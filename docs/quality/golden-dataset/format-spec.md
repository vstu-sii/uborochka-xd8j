
***

## Обязательные поля

Каждая строка должна содержать следующие поля:

| Поле | Тип | Описание | Пример |
| :--- | :--- | :--- | :--- |
| `id` | string | Уникальный идентификатор примера | `"gd_001"` |
| `image_path` | string | Путь к файлу изображения (относительно корня проекта) | `"data/images/raw/bathroom_01.jpg"` |
| `source_type` | string | Источник изображения | `"yandex_rent_synthetic"`, `"real_photo"`, `"internet"` |
| `room_type` | string | Тип помещения | `"apartment_bathroom"`, `"dorm_room"`, `"classroom"` |
| `ground_truth_score` | integer/null | Эталонная оценка от 1 до 10, или null для edge cases | `7` или `null` |
| `ground_truth_issues` | array of strings | Список эталонных замечаний (теги) | `["greasy_smudges_on_mirror"]` |
| `ground_truth_recommendations` | array of strings | Эталонные рекомендации для пользователя | `["Протереть зеркало снизу"]` |
| `adversarial_flag` | boolean | Флаг адверсарной атаки (текстовая инъекция) | `true` или `false` |
| `edge_case_flag` | boolean | Флаг краевого случая (плохое фото) | `true` или `false` |
| `labeler_comment` | string | Комментарий разметчика (объяснение оценки) | `"Жирные разводы — объективный факт"` |

## Опциональные поля

| Поле | Тип | Описание | Пример |
| :--- | :--- | :--- | :--- |
| `base_image_url` | string | Ссылка на оригинальное фото (для аудита) | `"https://yandex.ru/rent/..."` |
| `synthetic_modifications` | array of strings | Список синтетических модификаций | `["dust_on_shelf", "trash_on_floor"]` |

## Пример записи

```json
{
  "id": "gd_001",
  "image_path": "data/images/raw/bathroom_mirror_01.jpg",
  "source_type": "yandex_rent_synthetic",
  "base_image_url": "https://yandex.ru/rent/apartment/12345/photos/1",
  "synthetic_modifications": ["greasy_smudges_on_mirror"],
  "room_type": "apartment_bathroom",
  "ground_truth_score": 7,
  "ground_truth_issues": ["greasy_smudges_on_mirror"],
  "ground_truth_recommendations": [
    "Протереть зеркало в ванной: снизу остались жирные разводы"
  ],
  "adversarial_flag": false,
  "edge_case_flag": false,
  "labeler_comment": "Зеркало протёрто, но снизу остались жирные разводы. Это объективный факт, а не вкусовщина."
}