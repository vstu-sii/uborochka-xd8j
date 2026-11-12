from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def test_root_serves_prototype() -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "проверка качества уборки" in response.text


def test_inspection_calls_persistence_and_returns_demo_assessment(monkeypatch) -> None:
    saved = {}

    def fake_create_assessment(**kwargs):
        saved.update(kwargs)
        return {"id": 42}

    monkeypatch.setattr("src.main.create_assessment", fake_create_assessment)
    response = client.post(
        "/inspection",
        data={"room_id": "room-101", "maid_id": "maid-001"},
        files={"photo": ("room.jpg", b"image bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    assert response.json() == {
        "request_id": "42",
        "status": "scored",
        "result": {
            "score": 7,
            "recommendations": ["Демонстрационный результат: подключите AI-модель."],
            "confidence": "low",
            "model_used": "demo-stub",
            "is_demo": True,
        },
    }
    assert saved["maid_id"] == "maid-001"
    assert saved["room_id"] == "room-101"
    assert saved["assessment"].is_demo is True


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
