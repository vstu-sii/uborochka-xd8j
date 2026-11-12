"""
Точка расширения: сюда AI Engineer добавляет вызов модели, которая
по фото убранного помещения возвращает оценку 1-10 и рекомендации.

Держим сигнатуру стабильной, чтобы src/bot/ мог полагаться на неё
независимо от того, какая модель/промпт используется внутри.
"""

from dataclasses import dataclass


@dataclass
class CleaningAssessment:
    score: int
    recommendations: list[str]
    confidence: str
    model_used: str
    is_demo: bool


def analyze_photo(image_bytes: bytes) -> CleaningAssessment:
    """Return a clearly marked placeholder until the vision model is integrated."""
    if not image_bytes:
        raise ValueError("image_bytes must not be empty")

    return CleaningAssessment(
        score=7,
        recommendations=["Демонстрационный результат: подключите AI-модель."],
        confidence="low",
        model_used="demo-stub",
        is_demo=True,
    )
