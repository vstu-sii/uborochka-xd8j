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
