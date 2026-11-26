import asyncio
import logging
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

# Импортируем baseline-модель
import sys
sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.models.baseline import BaselineModel

logger = logging.getLogger(__name__)
router = APIRouter()

# КОНСТАНТЫ ВАЛИДАЦИИ (из ai-pipeline.md, Этап 1)
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ENUM ДЛЯ room_type (валидация входа)
class RoomType(str, Enum):
    bedroom = "bedroom"
    bathroom = "bathroom"
    kitchen = "kitchen"
    general = "general"


# SINGLETON МОДЕЛИ
# Создаём модель один раз при старте сервера, а не на каждый запрос.
# Это снижает latency (не переинициализируем GigaChat-клиент).
_model: BaselineModel | None = None


def get_model() -> BaselineModel:
    global _model
    if _model is None:
        _model = BaselineModel()
        logger.info("BaselineModel инициализирована (singleton)")
    return _model


# === ЭНДПОИНТ POST /inspection ===
@router.post("/inspection")
async def inspect_room(
    photo: UploadFile = File(..., description="Фото номера (jpeg/png/webp, до 10МБ)"),
    room_id: str = Form(..., description="ID номера"),
    maid_id: str = Form(..., description="ID горничной"),
    room_type: RoomType = Form(RoomType.general, description="Тип комнаты"),
) -> Dict[str, Any]:
    """
    Эндпоинт проверки качества уборки по фото.
    Контракт: api/openapi.yaml, POST /inspection.
    """
    # --- 1. ВАЛИДАЦИЯ ФОРМАТА (точка контроля #1) ---
    if photo.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail={
                "error": "unsupported_media_type",
                "message": f"Разрешены только: {sorted(ALLOWED_CONTENT_TYPES)}",
                "received": photo.content_type,
            },
        )

    # --- 2. ВАЛИДАЦИЯ РАЗМЕРА ---
    image_bytes = await photo.read()
    if len(image_bytes) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "payload_too_large",
                "message": f"Файл {len(image_bytes)} байт превышает лимит {MAX_FILE_SIZE}",
            },
        )

    if len(image_bytes) == 0:
        raise HTTPException(
            status_code=400,
            detail={"error": "empty_file", "message": "Файл пустой"},
        )

    #  3. ВАЛИДАЦИЯ ОБЯЗАТЕЛЬНЫХ ПОЛЕЙ
    if not room_id.strip() or not maid_id.strip():
        raise HTTPException(
            status_code=422,
            detail={"error": "invalid_input", "message": "room_id и maid_id обязательны"},
        )

    #  4. СОХРАНЯЕМ ВО ВРЕМЕННЫЙ ФАЙЛ
    suffix = Path(photo.filename or "photo.jpg").suffix or ".jpg"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    # 5. ASYNC-ВЫЗОВ МОДЕЛИ
    try:
        model = get_model()
        result = await asyncio.to_thread(
            model.analyze_photo,
            photo_path=tmp_path,
            room_type=room_type.value,
        )
    finally:
        # Всегда удаляем временный файл
        Path(tmp_path).unlink(missing_ok=True)

    #  6. ФОРМИРУЕМ ОТВЕТ ПО КОНТРАКТУ
    # retry_count — внутренняя метрика, не часть контракта, убираем
    response = {
        "request_id": result["request_id"],
        "result": result["result"],
    }

    return response