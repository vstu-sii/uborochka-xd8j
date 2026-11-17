import io

from fastapi.testclient import TestClient
from PIL import Image

from src.main import app

client = TestClient(app)


def make_png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (64, 64), (200, 200, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_root_serves_prototype() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "проверка качества уборки" in response.text


def test_inspection_calls_persistence_and_returns_assessment(monkeypatch) -> None:
    saved = {}
    monkeypatch.setattr("src.main.reserve_usage", lambda *_args: None)
    monkeypatch.setattr("src.main.token_usage_ratio", lambda *_args: 0.0)
    monkeypatch.setattr("src.main.add_usage_tokens", lambda *_args: None)

    def fake_create_assessment(**kwargs):
        saved.update(kwargs)
        return {"id": 42}

    monkeypatch.setattr("src.main.create_assessment", fake_create_assessment)
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.png", make_png(), "image/png")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "42"
    assert body["status"] == "scored"
    result = body["result"]
    assert 1 <= result["score"] <= 10
    assert result["model_used"] == "baseline-heuristic-v1"
    assert result["is_demo"] is False
    assert result["recommendations"]
    assert saved["maid_id"] == "maid-001"
    assert saved["room_id"] == "room-101"
    assert saved["assessment"].is_demo is False
    assert result["degraded"] is False


def test_inspection_rejects_corrupt_image() -> None:
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.jpg", b"not an image", "image/jpeg")},
    )

    assert response.status_code == 422
    assert "Не удалось прочитать" in response.json()["detail"]


def test_inspection_rejects_non_image_upload() -> None:
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("notes.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 400
    assert "JPEG, PNG или WebP" in response.json()["detail"]


def test_inspection_rejects_oversized_image() -> None:
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={
            "photo": (
                "room.jpg",
                b"x" * (10 * 1024 * 1024 + 1),
                "image/jpeg",
            )
        },
    )

    assert response.status_code == 413
    assert "10 МБ" in response.json()["detail"]


def test_health_returns_unavailable_without_database(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)

    response = client.get("/health")

    assert response.status_code == 503
    assert "Хранилище не настроено" in response.json()["detail"]


def test_inspection_returns_429_when_usage_limit_is_reached(monkeypatch) -> None:
    from backend.limits.service import UsageLimitExceeded

    def reject_request(*_args):
        raise UsageLimitExceeded("daily_requests", "Достигнут дневной лимит запросов.")

    monkeypatch.setattr("src.main.reserve_usage", reject_request)
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.png", make_png(), "image/png")},
    )

    assert response.status_code == 429
    assert "дневной лимит запросов" in response.json()["detail"]


def test_inspection_uses_fallback_at_eighty_percent(monkeypatch) -> None:
    from src.vision.analyze import CleaningAssessment

    saved = {}
    call = {}
    monkeypatch.setattr("src.main.reserve_usage", lambda *_args: None)
    monkeypatch.setattr("src.main.token_usage_ratio", lambda *_args: 0.8)
    monkeypatch.setattr("src.main.add_usage_tokens", lambda *_args: None)

    def fake_analyze(_photo, *, use_fallback):
        call["use_fallback"] = use_fallback
        assessment = CleaningAssessment(
            8, ["Готово"], "medium", "baseline-heuristic-v1", False, 10, True
        )
        return assessment, True, 0.01, "baseline"

    monkeypatch.setattr("src.main.analyze_with_degradation", fake_analyze)
    monkeypatch.setattr(
        "src.main.create_assessment",
        lambda **kwargs: (saved.update(kwargs) or {"id": 43}),
    )
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.png", make_png(), "image/png")},
    )

    assert response.status_code == 200
    assert call["use_fallback"] is True
    assert response.json()["result"]["degraded"] is True


def test_metrics_endpoint_exposes_request_and_usage_metrics() -> None:
    client.get("/")
    response = client.get("/metrics")

    assert response.status_code == 200
    assert "http_requests_total" in response.text
    assert "http_requests_total" in response.text
    assert "http_errors_total" in response.text
    assert "http_request_duration_seconds_bucket" in response.text
    assert "model_calls_total" in response.text
    assert "model_tokens_total" in response.text
    assert "limit_triggers_total" in response.text
    assert "guard_denied_total" in response.text


def test_production_inspection_requires_application_api_key(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.delenv("INSPECTION_API_KEY", raising=False)
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.png", make_png(), "image/png")},
    )

    assert response.status_code == 401
