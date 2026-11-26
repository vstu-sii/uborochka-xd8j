from fastapi import FastAPI
from backend.routers.ai import router as ai_router

app = FastAPI(
    title="Уборочка AI API",
    description="API для проверки качества уборки фото через GigaChat",
    version="1.0.0",
)

# Подключаем AI-роутер
app.include_router(ai_router)


@app.get("/health")
async def health():
    """Health check для мониторинга."""
    return {"status": "ok", "service": "uborochka-ai"}