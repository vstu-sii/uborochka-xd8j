import json
import time
import uuid
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

TRACES_FILE = Path("ml/tracing/traces.jsonl")


class TracedClient:
    """
    Обёртка над GigaChat client. Каждый вызов .chat() логируется
    в traces.jsonl с полным контекстом: промпт, ответ, latency, ошибки.
    """

    def __init__(self, client, model_name: str):
        self.client = client
        self.model_name = model_name
        TRACES_FILE.parent.mkdir(parents=True, exist_ok=True)

    def chat(self, chat_request, request_id: Optional[str] = None) -> Any:
        request_id = request_id or str(uuid.uuid4())
        start = time.time()

        # Сохраняем промпт (без base64 картинки — она огромная)
        prompt_snapshot = self._serialize_messages(chat_request)

        trace: Dict[str, Any] = {
            "trace_id": str(uuid.uuid4()),
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "model": self.model_name,
            "prompt": prompt_snapshot,
        }

        try:
            response = self.client.chat(chat_request)
            elapsed_ms = int((time.time() - start) * 1000)

            answer = response.choices[0].message.content if response.choices else ""
            usage = getattr(response, "usage", None)

            trace.update({
                "status": "success",
                "latency_ms": elapsed_ms,
                "answer": answer,
                "tokens_in": getattr(usage, "prompt_tokens", None) if usage else None,
                "tokens_out": getattr(usage, "completion_tokens", None) if usage else None,
                "total_tokens": getattr(usage, "total_tokens", None) if usage else None,
            })

        except Exception as e:
            elapsed_ms = int((time.time() - start) * 1000)
            trace.update({
                "status": "error",
                "latency_ms": elapsed_ms,
                "error": str(e),
            })

        # Пишем трейс в JSONL (одна строка = один вызов)
        with TRACES_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

        logger.info(f"[TRACE {trace['trace_id'][:8]}] {trace['status']} "
                    f"latency={trace['latency_ms']}ms")

        # Если была ошибка — пробрасываем её дальше (чтобы retry в baseline сработал)
        if trace["status"] == "error":
            raise Exception(trace["error"])

        return response

    def _serialize_messages(self, chat_request) -> list:
        """Превращает Messages в plain dict для лога (обрезает base64)."""
        result = []
        for msg in chat_request.messages:
            content = msg.content
            # Обрезаем длинные base64 (картинки) до "[IMAGE ~N bytes]"
            if isinstance(content, str) and "base64," in content:
                content = content.split("base64,")[0] + "base64,[IMAGE]"
            result.append({"role": msg.role, "content": content})
        return result


def read_traces(limit: int = 100) -> list:
    """Читает последние N трейсов из JSONL."""
    if not TRACES_FILE.exists():
        return []
    with TRACES_FILE.open("r", encoding="utf-8") as f:
        lines = f.readlines()
    return [json.loads(line) for line in lines[-limit:]]