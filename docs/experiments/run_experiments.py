import sys
import json
import csv
import time
from pathlib import Path
from datetime import datetime

sys.path.append(str(Path(__file__).resolve().parents[2]))
from ml.models.baseline import BaselineModel

GOLDEN_DATASET = [
    {"photo": "test.jpg", "room_id": "room-101", "maid_id": "maid-001", "room_type": "bedroom",
     "description": "Спальня"},
    {"photo": "test.jpg", "room_id": "room-202", "maid_id": "maid-002", "room_type": "bathroom",
     "description": "Ванная"},
    {"photo": "test.jpg", "room_id": "room-303", "maid_id": "maid-003", "room_type": "general",
     "description": "Общий план"},
]

model = BaselineModel()
results = []

for i, test in enumerate(GOLDEN_DATASET, 1):
    print(f" Тест {i}: {test['description']}")

    if not Path(test["photo"]).exists():
        print(f"Фото {test['photo']} нет, пропускаем!")
        continue

    start = time.time()
    res = model.analyze_photo(test["photo"], room_type=test["room_type"])

    metrics = {
        "test_id": i,
        "photo": test["photo"],
        "room_type": test["room_type"],
        "score": res["result"]["score"],
        "confidence": res["result"]["confidence"],
        "latency_ms": res["result"]["processing_time_ms"],
        "tokens_in": res["result"].get("tokens_in", 0),
        "tokens_out": res["result"].get("tokens_out", 0),
        "total_time_ms": int((time.time() - start) * 1000),
    }
    results.append(metrics)
    print(f"   Score: {metrics['score']}, Latency: {metrics['latency_ms']} мс, Токены out: {metrics['tokens_out']}")

# Сохраняем в CSV
csv_path = Path("docs/experiments/results.csv")
with open(csv_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=results[0].keys())
    writer.writeheader()
    writer.writerows(results)

print(f"\nСохранено в {csv_path}")
print(f"Средний Score: {sum(r['score'] for r in results) / len(results):.1f}")
print(f"Средняя Latency: {sum(r['latency_ms'] for r in results) / len(results):.0f} мс")