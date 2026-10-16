"""
Hello-world заглушка прода.

Даёт:
- публичный URL, который открывается у любого члена команды (/)
- health-check для CI/хостинга и docker-compose healthcheck (/health)
- заготовку под Telegram webhook (/webhook/telegram) — логику разбора
  фото и вызова AI-модели добавляет AI Engineer в src/vision/.

Цель по DoD блока Delivery: прод существует с первой недели, дальше
он только наращивается — не переписывается с нуля.
"""

from fastapi import FastAPI, Request

app = FastAPI(title="Cleaning Quality Bot")


@app.get("/")
def root() -> dict:
    return {
        "status": "ok",
        "service": "cleaning-quality-bot",
        "message": "Hello world in prod — фундамент готов, логика наращивается сверху.",
    }


@app.get("/health")
def health() -> dict:
    return {"status": "healthy"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request) -> dict:
    """Заготовка под приём апдейтов от Telegram.

    TODO(AI Engineer / Product): подключить python-telegram-bot,
    разобрать фото из апдейта, передать в src/vision для анализа,
    вернуть оценку и рекомендации пользователю.
    """
    _ = await request.json()
    return {"status": "received"}
