"""FastAPI application for the cleaning assessment prototype."""

from pathlib import Path

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.storage import DatabaseNotConfigured, check_database, create_assessment
from src.vision.analyze import analyze_photo

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
PROTOTYPE_DIR = Path(__file__).resolve().parents[1] / "frontend" / "prototype"

app = FastAPI(title="Cleaning Quality Bot")
app.mount(
    "/prototype",
    StaticFiles(directory=PROTOTYPE_DIR),
    name="prototype",
)


@app.get("/")
def root() -> FileResponse:
    return FileResponse(PROTOTYPE_DIR / "index.html")


@app.get("/health")
def health() -> dict:
    try:
        check_database()
    except DatabaseNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Хранилище не настроено. Укажите DATABASE_URL.",
        ) from error
    except psycopg.OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="База данных временно недоступна.",
        ) from error
    return {"status": "healthy"}


@app.post("/inspection")
async def inspect_photo(
    photo: UploadFile = File(...),
    room_id: str = Form(..., min_length=1, max_length=100),
    maid_id: str = Form(..., min_length=1, max_length=100),
) -> dict:
    if photo.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(
            status_code=400,
            detail="Загрузите изображение в формате JPEG, PNG или WebP.",
        )

    image_bytes = await photo.read(MAX_IMAGE_SIZE + 1)
    if not image_bytes:
        raise HTTPException(status_code=400, detail="Файл изображения пуст.")
    if len(image_bytes) > MAX_IMAGE_SIZE:
        raise HTTPException(
            status_code=413, detail="Размер изображения превышает 10 МБ."
        )

    assessment = analyze_photo(image_bytes)
    try:
        saved = create_assessment(
            maid_id=maid_id,
            room_id=room_id,
            image_name=photo.filename or "upload",
            assessment=assessment,
        )
    except DatabaseNotConfigured as error:
        raise HTTPException(
            status_code=503,
            detail="Хранилище не настроено. Укажите DATABASE_URL.",
        ) from error
    except psycopg.OperationalError as error:
        raise HTTPException(
            status_code=503,
            detail="База данных временно недоступна.",
        ) from error

    return {
        "request_id": str(saved["id"]),
        "status": "scored",
        "result": {
            "score": assessment.score,
            "recommendations": assessment.recommendations,
            "confidence": assessment.confidence,
            "model_used": assessment.model_used,
            "is_demo": assessment.is_demo,
        },
    }


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Acknowledge Telegram updates until bot orchestration is integrated."""
    _ = await request.json()
    return {"status": "received"}
