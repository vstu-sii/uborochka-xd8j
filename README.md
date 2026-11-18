# Оценка качества уборки по фото (AI-бот)

Telegram-бот: пользователь присылает фото убранного помещения,
AI-модель анализирует чистоту/порядок и выставляет оценку от 1 до 10
с конкретными рекомендациями («протереть пыль на полке»,
«пропылесосить под кроватью»).

Целевая аудитория: клининговые службы, управляющие компании (приёмка
работы после смены)

## Статус CI

![CI](https://github.com/vstu-sii/uborochka-xd8j/actions/workflows/ci.yml/badge.svg)

## Прод

Публичный URL Render: **`https://uborochka-xd8j.onrender.com`**.
Настройки деплоя описаны в [docs/deploy.md](docs/deploy.md). Этот URL ранее
обслуживал только health-check; проверяйте `/health` после каждого деплоя.
/health возвращает 200, если база доступна, иначе 503
Продакшен: https://uborochka-xd8j.onrender.com (Render, первый запрос после
простоя может занять до 50 секунд). Фактический статус сервиса проверяйте
по `/health`.

## Как поднять проект локально (dev)

Требования: Docker + Docker Compose.

```bash
cp .env.example .env
# локально секреты не нужны для baseline-эвристики; Gemini включается отдельно
docker compose up --build
```

Миграции БД применяются при старте. Интерфейс: `http://localhost:8000`,
API документация: `http://localhost:8000/docs`, health-check —
`http://localhost:8000/health`. Фото отправляются в `POST /inspection`
и сведения о проверке сохраняются в PostgreSQL. Загруженные изображения
не сохраняются.

По умолчанию анализ выполняет baseline-эвристика (Pillow); это ограниченная
эвристическая оценка, а не профессиональная приёмка качества. Gemini Flash-Lite
можно включить отдельно через `GEMINI_ENABLED` и `GEMINI_API_KEY`.

Время подъёма окружения должно быть < 10 минут. Если дольше — это баг,
заводи issue.

## Структура репозитория

```
.
├── src/                    # код приложения
│   ├── main.py              # FastAPI-приложение и API оценки
│   ├── bot/                  # логика Telegram-бота
│   └── vision/                # обёртка над AI-моделью для анализа фото
├── compose.yml              # API, PostgreSQL и миграции
├── compose.staging.yml      # изолированный staging поверх локального Compose
├── backend/                 # лимиты, guards, модельные провайдеры, метрики
├── monitoring/              # Prometheus, Loki, Tempo, Alloy, Grafana
├── docs/
│   ├── deploy.md            # CI/CD, Render и откат
│   ├── environments.md      # local/staging/prod
│   ├── lab4-delivery.md     # DoD и команды проверки Lab 4
│   └── agent-workflow.md    # отчёт DELIVERY
├── .github/
│   ├── workflows/ci.yml     # CI на PR и push
│   ├── workflows/deploy.yml # проверки, сборка и автодеплой
│   └── workflows/rollback.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── Dockerfile                # прод-образ
├── requirements.txt
├── .env.example
└── README.md
```

## Команда

| Роль | Имя | Зона ответственности |
|---|---|---|
| Product / VO |Малеев Егор | Область и границы, требования, чек-лист приёмки |
| AI Engineer |Лукьянова Екатерина | Логика оценки поверх модели, промпты, качество ответа |
| Delivery |Лопушкова Арина | Репозиторий, CI/CD, деплой, прод с первой недели |
| Quality & Safety |Земляная Мария | Критерии успеха, проверяемость, защита от инъекций через фото |

## Как контрибьютить

1. Ветка от `main`: `feature/<короткое-описание>` или `fix/<короткое-описание>`
2. PR по шаблону из `.github/PULL_REQUEST_TEMPLATE.md`
3. CI (lint, format, build) обязателен для мёржа
4. Секреты — только в игнорируемом `.env`, GitHub Secrets или Render env vars,
   никогда не коммитить в код

## Lab 4: staging и мониторинг

Staging поднимается теми же сервисами Compose, но с отдельными БД, томом и
портами:

```bash
cp .env.staging.example .env.staging
docker compose -f compose.yml -f compose.staging.yml up --build
```

Для локального мониторинга:

```bash
cp monitoring/metrics_token.example monitoring/metrics_token
docker compose -f compose.yml -f monitoring/compose.monitoring.yml up --build
```

Grafana: <http://localhost:3000> (`admin` / `change-me` только для локального
стека). Описание dashboard, лимитов, CI/CD и того, что ещё требует ручной
проверки: [docs/lab4-delivery.md](docs/lab4-delivery.md).
