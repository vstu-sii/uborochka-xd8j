"""
Точка расширения: сюда AI Engineer добавляет вызов модели, которая
по фото убранного помещения возвращает оценку 1-10 и рекомендации.

Держим сигнатуру стабильной, чтобы src/bot/ мог полагаться на неё
независимо от того, какая модель/промпт используется внутри.
"""

from dataclasses import dataclass


@dataclass
class CleaningAssessment:
    score: int  # 1..10
    recommendations: list[str]


def analyze_photo(image_bytes: bytes) -> CleaningAssessment:
    """TODO: заменить заглушку на реальный вызов AI-модели.

    Возвращает заглушечную оценку, чтобы hello-world конец в конец
    работал уже сейчас.
    """
    return CleaningAssessment(
        score=0,
        recommendations=["Анализ ещё не подключён — это заглушка."],
    )
