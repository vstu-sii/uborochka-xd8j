"""FastAPI application for the cleaning assessment prototype."""

import json
import logging
import os
from pathlib import Path
from time import perf_counter

import psycopg
from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.guards.actions import GuardDenied, authorize_caller
from backend.limits.service import (
    UsageLimitExceeded,
    UsageStorageUnavailable,
    TOKEN_RESERVATION_PER_IMAGE,
    add_usage_tokens,
    reserve_usage,
    token_usage_ratio,
)
from backend.observability import (
    HTTP_ERRORS_TOTAL,
    HTTP_REQUEST_DURATION_SECONDS,
    HTTP_REQUESTS_TOTAL,
)
from backend.providers import (
    ProviderConfigurationError,
    analyze_with_degradation,
    validate_provider_configuration,
)
from src.storage import DatabaseNotConfigured, check_database, create_assessment
from src.vision.analyze import validate_image

MAX_IMAGE_SIZE = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
PROTOTYPE_DIR = Path(__file__).resolve().parents[1] / "frontend" / "prototype"


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        event = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname.lower(),
            "event": getattr(record, "event", record.getMessage()),
            "message": record.getMessage(),
        }
        for key in (
            "endpoint",
            "method",
            "status_code",
            "latency_seconds",
            "user_id",
            "action",
            "limit",
            "score",
            "model",
            "degraded",
            "tokens",
        ):
            if hasattr(record, key):
                event[key] = getattr(record, key)
        span_context = trace.get_current_span().get_span_context()
        if span_context.is_valid:
            event["trace_id"] = f"{span_context.trace_id:032x}"
        return json.dumps(event, ensure_ascii=False)


handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    handlers=[handler],
    force=True,
)
logger = logging.getLogger("uborochka")
provider = TracerProvider(resource=Resource.create({"service.name": "uborochka-api"}))
otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
if otlp_endpoint:
    provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
    )
trace.set_tracer_provider(provider)

app = FastAPI(title="Cleaning Quality Bot")
FastAPIInstrumentor.instrument_app(app)
app.mount(
    "/prototype",
    StaticFiles(directory=PROTOTYPE_DIR),
    name="prototype",
)


@app.middleware("http")
async def observe_requests(request: Request, call_next):
    started = perf_counter()
    response = await call_next(request)
    elapsed = perf_counter() - started
    route = request.scope.get("route")
    endpoint = getattr(route, "path", "unmatched")
    if endpoint != "/metrics":
        status = str(response.status_code)
        HTTP_REQUESTS_TOTAL.labels(endpoint=endpoint, status=status).inc()
        if response.status_code >= 400:
            HTTP_ERRORS_TOTAL.labels(endpoint=endpoint, status=status).inc()
        HTTP_REQUEST_DURATION_SECONDS.labels(endpoint=endpoint).observe(elapsed)
    logger.info(
        "request_finished",
        extra={
            "event": "request",
            "endpoint": endpoint,
            "method": request.method,
            "status_code": response.status_code,
            "latency_seconds": round(elapsed, 6),
        },
    )
    return response


@app.get("/")
def root() -> FileResponse:
    return FileResponse(PROTOTYPE_DIR / "index.html")


@app.get("/metrics", include_in_schema=False)
def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


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
    return {"status": "healthy", "commit": os.getenv("RENDER_GIT_COMMIT") or None}


@app.post("/inspection")
async def inspect_photo(
    request: Request,
    photo: UploadFile = File(...),
    room_id: str = Form(..., min_length=1, max_length=100),
    maid_id: str = Form(..., min_length=1, max_length=100),
) -> dict:
    try:
        authorize_caller(request.headers.get("X-API-Key"), user_id=maid_id)
    except GuardDenied as error:
        raise HTTPException(
            status_code=401, detail="Нет доступа к выполнению проверки."
        ) from error

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

    try:
        validate_image(image_bytes)
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="Не удалось прочитать изображение. Загрузите другое фото.",
        ) from error

    try:
        validate_provider_configuration()
    except ProviderConfigurationError as error:
        raise HTTPException(
            status_code=503, detail="Провайдер модели не настроен."
        ) from error

    estimated_tokens = TOKEN_RESERVATION_PER_IMAGE
    try:
        reserve_usage(maid_id, estimated_tokens)
        degraded = token_usage_ratio(maid_id) >= 0.8
        assessment, degraded, _, provider_name = analyze_with_degradation(
            image_bytes, use_fallback=degraded
        )
        add_usage_tokens(maid_id, estimated_tokens, assessment.tokens_used)
    except UsageLimitExceeded as error:
        logger.warning(
            "usage_limit_triggered",
            extra={
                "event": "limit_triggered",
                "user_id": maid_id,
                "limit": error.limit,
            },
        )
        raise HTTPException(status_code=429, detail=error.message) from error
    except (UsageStorageUnavailable, psycopg.OperationalError) as error:
        raise HTTPException(
            status_code=503, detail="Сервис лимитов временно недоступен."
        ) from error
    except ValueError as error:
        raise HTTPException(
            status_code=422,
            detail="Не удалось прочитать изображение. Загрузите другое фото.",
        ) from error

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
    except GuardDenied as error:
        raise HTTPException(
            status_code=403, detail="Операция запрещена политикой приложения."
        ) from error

    logger.info(
        "inspection_completed",
        extra={
            "event": "inspection_completed",
            "user_id": maid_id,
            "score": assessment.score,
            "model": assessment.model_used,
            "degraded": degraded,
            "tokens": assessment.tokens_used,
        },
    )
    return {
        "request_id": str(saved["id"]),
        "status": "scored",
        "result": {
            "score": assessment.score,
            "recommendations": assessment.recommendations,
            "confidence": assessment.confidence,
            "model_used": assessment.model_used,
            "is_demo": assessment.is_demo,
            "degraded": degraded,
            "provider": provider_name,
            "tokens_used": assessment.tokens_used,
        },
    }


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Acknowledge Telegram updates until bot orchestration is integrated."""
    _ = await request.json()
    return {"status": "received"}
