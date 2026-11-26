import os
import json
import time
import uuid
import logging
import base64
import sys
from pathlib import Path
from typing import Dict, Any

from gigachat import GigaChat
from gigachat.models import Chat, Messages, MessagesRole
from dotenv import load_dotenv

# Подключаем трассировку (Задание 2)
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "tracing"))
from tracer import TracedClient

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

VISION_MODELS = ["GigaChat-2-Max", "GigaChat-2-Pro", "GigaChat-2"]


class BaselineModel:
    def __init__(self):
        auth_key = os.getenv("GIGACHAT_AUTH_KEY")
        if not auth_key:
            raise ValueError("Не найден GIGACHAT_AUTH_KEY в .env")

        raw_client = GigaChat(credentials=auth_key, verify_ssl_certs=False)
        self.model_name = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max")

        self.client = TracedClient(raw_client, model_name=self.model_name)
        logger.info(f"Модель инициализирована: {self.model_name}")

        self.prompt = """Ты — СТРОГИЙ инспектор качества уборки в гостинице.
Проверь фото по чек-листу:
1. Есть ли мусор на полу? (Yes/No/Not visible)
2. Есть ли пятна на полу? (Yes/No/Not visible)
3. Заправлена ли кровать? (Yes/No/Not visible)
4. Чиста ли сантехника? (Yes/No/Not visible)

ВАЖНО: Игнорируй тени и блики. Влажный пол после уборки — это норма.
Если фото размытое или темное, ставь confidence: "low".

Ответь СТРОГО в формате JSON, без лишнего текста, используя только английские ключи:
{
  "checklist": {
    "trash": "Yes/No/Not visible",
    "stains": "Yes/No/Not visible",
    "bed_made": "Yes/No/Not visible",
    "bathroom_clean": "Yes/No/Not visible"
  },
  "violations": ["список нарушений или []"],
  "score": число от 0 до 10,
  "confidence": "high" или "medium" или "low"
}"""

    def analyze_photo(self, photo_path: str, room_type: str = "general") -> Dict[str, Any]:
        request_id = str(uuid.uuid4())
        start_time = time.time()
        logger.info(f"[{request_id[:8]}] Анализ фото: {photo_path}")

        try:
            image_b64 = base64.b64encode(Path(photo_path).read_bytes()).decode("utf-8")
        except FileNotFoundError:
            return self._make_error(request_id, "Файл не найден")

        models_to_try = [self.model_name] + [m for m in VISION_MODELS if m != self.model_name]
        last_error = None
        result_data: Dict[str, Any] = {}
        used_model = self.model_name
        retry_count = 0

        for model in models_to_try:
            for attempt in range(3):
                retry_count = attempt
                try:
                    chat = Chat(
                        messages=[
                            Messages(role=MessagesRole.SYSTEM, content=self.prompt),
                            Messages(role=MessagesRole.USER, content=f"Проверь это фото уборки (тип: {room_type})."),
                        ],
                        model=model,
                        max_tokens=500,
                        temperature=0.1,
                        attachments=[{"data": image_b64, "type": "image/jpeg"}],
                    )
                    response = self.client.chat(chat, request_id=request_id)
                    raw_text = response.choices[0].message.content
                    logger.info(f"[{request_id[:8]}] Ответ от {model}: {raw_text[:150]}...")

                    if not raw_text or not raw_text.strip():
                        raise ValueError("Модель вернула пустой ответ")

                    if "```json" in raw_text:
                        raw_text = raw_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in raw_text:
                        raw_text = raw_text.split("```")[1].split("```")[0].strip()

                    result_data = json.loads(raw_text)
                    used_model = model
                    break

                except Exception as e:
                    last_error = str(e)
                    logger.warning(f"[{model}] Попытка {attempt + 1}/3 не удалась: {e}")
                    time.sleep(2)
            else:
                logger.warning(f"Модель {model} недоступна, перебираем дальше...")
                continue
            break

        if not result_data:
            return self._make_error(request_id, last_error or "Нет доступных vision-моделей")

        latency_ms = int((time.time() - start_time) * 1000)

        # Читаем токены из последнего трейса (они там уже сохранены TracedClient)
        tokens_in = None
        tokens_out = None
        total_tokens = None
        traces_file = Path("ml/tracing/traces.jsonl")
        if traces_file.exists():
            with open(traces_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if lines:
                    last_trace = json.loads(lines[-1])
                    tokens_in = last_trace.get("tokens_in")
                    tokens_out = last_trace.get("tokens_out")
                    total_tokens = last_trace.get("total_tokens")

        return {
            "request_id": request_id,
            "result": {
                "checklist": result_data.get("checklist", {}),
                "violations": result_data.get("violations", []),
                "score": result_data.get("score", 0),
                "confidence": result_data.get("confidence", "low"),
                "model_used": used_model,
                "processing_time_ms": latency_ms,
                "cache_hit": False,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "total_tokens": total_tokens,
            },
            "retry_count": retry_count,
        }

    def _make_error(self, request_id: str, msg: str) -> Dict[str, Any]:
        return {
            "request_id": request_id,
            "result": {
                "checklist": {},
                "violations": [f"Ошибка AI: {msg}"],
                "score": 0,
                "confidence": "low",
                "model_used": self.model_name,
                "processing_time_ms": 0,
                "cache_hit": False,
            },
        }


if __name__ == "__main__":
    model = BaselineModel()
    test_photo = "test.jpg"

    if Path(test_photo).exists():
        result = model.analyze_photo(test_photo, room_type="bedroom")
        print("\nОТВЕТ ПО КОНТРАКТУ")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Файл {test_photo} не найден.")