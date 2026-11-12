"""
Точка расширения: сюда AI Engineer добавляет вызов модели, которая
по фото убранного помещения возвращает оценку 1-10 и рекомендации.

Держим сигнатуру стабильной, чтобы src/bot/ мог полагаться на неё
независимо от того, какая модель/промпт используется внутри.

Сейчас внутри baseline-эвристика: оценка по яркости и «загромождённости»
кадра (плотность границ). Это не нейросеть, а простая замена, пока не
подключена vision-модель.
"""

import io
from dataclasses import dataclass

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

MODEL_NAME = "baseline-heuristic-v1"


@dataclass
class CleaningAssessment:
    score: int
    recommendations: list[str]
    confidence: str
    model_used: str
    is_demo: bool


def analyze_photo(image_bytes: bytes) -> CleaningAssessment:
    """Baseline: оценка по яркости и «загромождённости» кадра (плотность границ)."""
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")

    try:
        image = Image.open(io.BytesIO(image_bytes)).convert("L")
    except (UnidentifiedImageError, OSError) as error:
        raise ValueError("image_bytes is not a valid image") from error

    image.thumbnail((256, 256))
    brightness = ImageStat.Stat(image).mean[0] / 255
    clutter = ImageStat.Stat(image.filter(ImageFilter.FIND_EDGES)).mean[0] / 255

    raw_score = 10.0 - clutter * 40
    too_dark = brightness < 0.25
    too_bright = brightness > 0.85
    if too_dark or too_bright:
        raw_score -= 3
    score = max(1, min(10, round(raw_score)))

    recommendations: list[str] = []
    if clutter > 0.08:
        recommendations.append(
            "На фото много мелких деталей: уберите лишние предметы с поверхностей."
        )
    if too_dark:
        recommendations.append(
            "Фото слишком тёмное: переснимите при хорошем освещении."
        )
    if too_bright:
        recommendations.append("Фото пересвечено: переснимите без прямого света.")
    if not recommendations:
        recommendations.append("Явных проблем по базовым признакам не обнаружено.")

    return CleaningAssessment(
        score=score,
        recommendations=recommendations,
        confidence="low" if (too_dark or too_bright) else "medium",
        model_used=MODEL_NAME,
        is_demo=False,
    )
