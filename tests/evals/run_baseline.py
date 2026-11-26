"""
Прогон baseline evals на GigaChat-2-Max Vision.
Запуск: python tests/evals/run_baseline.py
"""

import json
import os
import time
import base64
import urllib3
from typing import List, Dict, Any

import requests
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from config import GIGACHAT_CONFIG, SYSTEM_PROMPT, DATASET_PATH, REPORT_PATH
from metrics import (
    calculate_score_delta,
    calculate_issue_recall,
    calculate_false_positive_rate,
    calculate_injection_rejection,
    calculate_graceful_degradation,
    calculate_format_validation,
)

load_dotenv()


def get_gigachat_token() -> str:
    client_id = os.getenv(GIGACHAT_CONFIG["client_id_env"])
    client_secret = os.getenv(GIGACHAT_CONFIG["client_secret_env"])

    if not client_id or not client_secret:
        raise ValueError("GIGACHAT_CLIENT_ID и GIGACHAT_CLIENT_SECRET не найдены в .env")

    auth_string = f"{client_id}:{client_secret}"
    auth_base64 = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_base64}",
        "RqUID": os.urandom(16).hex(),
        "Content-Type": "application/x-www-form-urlencoded",
    }

    response = requests.post(
        f"{GIGACHAT_CONFIG['base_url']}/oauth",
        headers=headers,
        data={"scope": GIGACHAT_CONFIG["scope"]},
        timeout=GIGACHAT_CONFIG["timeout"],
        verify=False,
    )

    if response.status_code != 200:
        raise Exception(f"Ошибка получения токена: {response.status_code} {response.text}")

    return response.json()["access_token"]


def encode_image(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")


def call_gigachat_vision(image_path: str, token: str) -> Dict[str, Any]:
    """Вызов GigaChat-2-Max Vision API."""
    try:
        if not os.path.exists(image_path):
            return {
                "score": None,
                "status": "error",
                "issues": ["file_not_found"],
                "recommendations": [f"Файл не найден: {image_path}"],
                "confidence": 0,
            }

        base64_image = encode_image(image_path)

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": GIGACHAT_CONFIG["model"],
            "messages": [
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": "Оцени чистоту и порядок на этом фото. Верни строго JSON по формату из системного промпта.",
                    "attachments": [
                        {
                            "type": "IMAGE",
                            "data": f"data:image/jpeg;base64,{base64_image}",
                        }
                    ],
                },
            ],
            "max_tokens": GIGACHAT_CONFIG["max_tokens"],
            "temperature": GIGACHAT_CONFIG["temperature"],
        }

        response = requests.post(
            f"{GIGACHAT_CONFIG['base_url']}/chat/completions",
            headers=headers,
            json=payload,
            timeout=GIGACHAT_CONFIG["timeout"],
            verify=False,
        )

        if response.status_code != 200:
            return {
                "score": None,
                "status": "api_error",
                "issues": [],
                "recommendations": [f"Ошибка API: {response.status_code} - {response.text[:200]}"],
                "confidence": 0,
            }

        content = response.json()["choices"][0]["message"]["content"]

        # Извлекаем JSON из markdown-обёртки
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        result = json.loads(content)
        return result

    except json.JSONDecodeError as e:
        return {
            "score": None,
            "status": "parse_error",
            "issues": [],
            "recommendations": [f"Ошибка парсинга: {str(e)}"],
            "confidence": 0,
        }
    except Exception as e:
        return {
            "score": None,
            "status": "api_error",
            "issues": [],
            "recommendations": [f"Ошибка: {str(e)}"],
            "confidence": 0,
        }


def load_dataset(path: str) -> List[Dict]:
    """Загрузка Golden Dataset из JSONL."""
    dataset = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                dataset.append(json.loads(line))
    return dataset


def generate_mock_prediction(example: Dict) -> Dict:
    gt = example
    gt_score = gt.get("ground_truth_score")
    gt_issues = gt.get("ground_truth_issues", [])
    is_adversarial = gt.get("adversarial_flag", False)
    is_edge_case = gt.get("edge_case_flag", False)

    if is_edge_case:
        if gt["id"] in ["gd_004", "gd_011"]:
            return {
                "score": None,
                "status": "needs_better_photo",
                "issues": [],
                "recommendations": ["Недостаточно света. Переснимите при хорошем освещении."],
                "confidence": 0.9,
            }
        else:
            return {
                "score": 4,
                "status": "ok",
                "issues": ["dust", "trash"],
                "recommendations": ["Убрать мусор", "Протереть пыль"],
                "confidence": 0.6,
            }

    if is_adversarial:
        if gt["id"] in ["gd_002", "gd_008"]:
            return {
                "score": 3,
                "status": "ok",
                "issues": gt_issues + ["adversarial_text_detected"],
                "recommendations": ["Убрать манипулятивный текст", "Оценить реальное состояние"],
                "confidence": 0.85,
            }
        else:
            return {
                "score": 9,
                "status": "ok",
                "issues": [],
                "recommendations": ["Уборка выполнена качественно"],
                "confidence": 0.7,
            }

    import random
    random.seed(hash(gt["id"]) % 1000)
    noise = random.choice([-1, 0, 0, 0, 1])
    pred_score = max(1, min(10, gt_score + noise)) if gt_score else None

    found_issues = gt_issues[:max(1, len(gt_issues) - 1)]
    false_issues = ["dust"] if "dust" not in gt_issues else []

    return {
        "score": pred_score,
        "status": "ok",
        "issues": found_issues + false_issues,
        "recommendations": [f"Рекомендация по: {issue}" for issue in found_issues + false_issues],
        "confidence": 0.75,
    }


def analyze_errors(predictions: List[Dict]) -> Dict:
    """Анализ распределения ошибок."""
    failures = []

    for p in predictions:
        pred = p["prediction"]
        gt = p["ground_truth"]

        if gt.get("ground_truth_score") is not None and pred.get("score") is not None:
            delta = abs(pred["score"] - gt["ground_truth_score"])
            if delta > 1:
                failures.append({
                    "id": gt["id"],
                    "type": "score_delta",
                    "reason": f"Оценка ИИ={pred['score']}, эталон={gt['ground_truth_score']} (delta={delta})",
                    "room_type": gt.get("room_type"),
                })

        gt_issues = set(gt.get("ground_truth_issues", []))
        pred_issues = set(pred.get("issues", []))
        missed = gt_issues - pred_issues
        if missed:
            failures.append({
                "id": gt["id"],
                "type": "missed_issues",
                "reason": f"Пропущены: {missed}",
                "room_type": gt.get("room_type"),
            })

        false_positives = pred_issues - gt_issues
        if false_positives and not gt.get("edge_case_flag"):
            failures.append({
                "id": gt["id"],
                "type": "false_positives",
                "reason": f"Выдуманы: {false_positives}",
                "room_type": gt.get("room_type"),
            })

    room_failures = {}
    for f in failures:
        room = f.get("room_type", "unknown")
        room_failures[room] = room_failures.get(room, 0) + 1

    return {
        "total_failures": len(failures),
        "by_room_type": room_failures,
        "by_failure_type": {
            "score_delta": len([f for f in failures if f["type"] == "score_delta"]),
            "missed_issues": len([f for f in failures if f["type"] == "missed_issues"]),
            "false_positives": len([f for f in failures if f["type"] == "false_positives"]),
        },
        "top_failures": failures[:10],
    }


def run_baseline_evals():
    """Главная функция прогона baseline."""
    print("Запуск BASELINE EVALS на GIGACHAT-2-MAX VISION")

    print(f"\n[1/4] Загрузка датасета из {DATASET_PATH}...")
    dataset = load_dataset(DATASET_PATH)
    print(f"    Загружено примеров: {len(dataset)}")

    print("\n[2/4] Инициализация GigaChat-2-Max Vision...")
    use_mock = False
    token = None

    try:
        token = get_gigachat_token()
        print(f"    Токен получен. Модель: {GIGACHAT_CONFIG['model']}")
    except ValueError as e:
        print(f"     {e}")
        print("    Запускаем MOCK-режим...(на крайняк)")
        use_mock = True
    except Exception as e:
        print(f"     Ошибка подключения: {e}")
        print("    Запускаем MOCK-режим...(на крайняк)")
        use_mock = True

    print("\n[3/4] Прогон evals...")
    predictions = []
    start_time = time.time()

    for i, example in enumerate(dataset, 1):
        image_path = example["image_path"]

        if use_mock:
            prediction = generate_mock_prediction(example)
        else:
            prediction = call_gigachat_vision(image_path, token)

        predictions.append({
            "id": example["id"],
            "prediction": prediction,
            "ground_truth": example,
        })

        if i % 5 == 0 or i == len(dataset):
            print(f"    Обработано: {i}/{len(dataset)}")

    total_time = time.time() - start_time
    print(f"    Общее время: {total_time:.2f} сек")

    print("\n[4/4] Подсчёт метрик...")
    preds_only = [p["prediction"] for p in predictions]
    gts_only = [p["ground_truth"] for p in predictions]

    metrics = {
        "score_delta": calculate_score_delta(preds_only, gts_only),
        "issue_recall": calculate_issue_recall(preds_only, gts_only),
        "false_positive_rate": calculate_false_positive_rate(preds_only, gts_only),
        "injection_rejection": calculate_injection_rejection(preds_only, gts_only),
        "graceful_degradation": calculate_graceful_degradation(preds_only, gts_only),
        "format_validation": calculate_format_validation(preds_only),
    }

    error_analysis = analyze_errors(predictions)

    report = {
        "metadata": {
            "dataset_version": "v1",
            "dataset_size": len(dataset),
            "model": GIGACHAT_CONFIG["model"],
            "provider": "GigaChat-2-Max (Sber)",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "mode": "mock" if use_mock else "live",
            "total_time_sec": round(total_time, 2),
        },
        "metrics": metrics,
        "error_analysis": error_analysis,
        "predictions": predictions,
    }

    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n Отчёт сохранён: {REPORT_PATH}")
    print("Сводка по метрикам")

    for metric_name, metric_value in metrics.items():
        status = "PASS" if metric_value.get("pass", True) else "FAIL"
        print(f"{status} {metric_name}: {metric_value}")

    print("Где модель врет (топ проблем)")
    for issue in error_analysis["top_failures"][:5]:
        print(f"  - {issue['id']}: {issue['reason']}")

    return report


if __name__ == "__main__":
    run_baseline_evals()