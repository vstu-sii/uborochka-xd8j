# Lab 4 — Delivery: production-ready infrastructure

| Пункт DoD | Где реализовано | Как проверить (команда) |
|---|---|---|
| Merge в `main` после зелёных тестов и Docker build инициирует production deployment | `.github/workflows/deploy.yml`, `docs/deploy.md` | GitHub Actions после merge; нужен secret `RENDER_DEPLOY_HOOK_URL` и Render Auto-Deploy Off |
| Health-check после deploy с повторами; ошибка делает workflow красным | `.github/workflows/deploy.yml` | Проверить `Wait for production health check` в Actions |
| Откат конкретного commit SHA доступен одной командой и через Actions | `scripts/rollback.sh`, `.github/workflows/rollback.yml`, `docs/deploy.md` | `RENDER_DEPLOY_HOOK_URL=... scripts/rollback.sh <git-sha>` |
| Staging повторяет prod-образ и Compose-сервисы, изолируя порты, БД и volume | `compose.yml`, `compose.staging.yml`, `docs/environments.md` | `docker compose -f compose.yml -f compose.staging.yml config` |
| Дашборд показывает запросы/ошибки/latency, usage, логи и ссылку на трейсы | `monitoring/`, `monitoring/grafana/dashboards/uborochka.json` | Поднять monitoring compose и открыть Grafana; см. `monitoring/README.md` |
| Дневные лимиты запросов/токенов и месячный бюджет хранятся в PostgreSQL | `backend/limits/`, `database/migrations/0003_usage_limits.sql` | `pytest -q tests/test_limits_and_guards.py`; интеграционный staging-прогон описан в `monitoring/README.md` |
| Аномальный расход токенов и срабатывание пользовательских лимитов имеют независимые Grafana alerts | `monitoring/grafana/provisioning/alerting/alerts.yml`, `scripts/simulate_anomaly.py` | Gemini включён: проверка токенов; baseline без ключа: шестой запрос срабатывает на alert лимита. Параметры и расчёт порога — `monitoring/README.md` |
| Модель не выполняет операции; приложение проверяет allow-list перед записью | `backend/guards/`, `src/storage.py` | `pytest -q tests/test_limits_and_guards.py` |
| `/metrics` публикует HTTP, model, token, limit и guard metrics | `backend/observability.py`, `src/main.py` | `curl -fsS http://localhost:8000/metrics` |
| Структурированные события выводятся в stdout; FastAPI и `llm.call` spans экспортируются в Tempo | `src/main.py`, `backend/providers.py`, `monitoring/` | Смотреть Docker logs и Tempo после запуска monitoring compose |

## Предчек перед приёмкой

- [ ] GitHub secret `RENDER_DEPLOY_HOOK_URL` задан; Render service связан с
  `main`, `Auto-Deploy` выключен, env vars и DB настроены.
- [ ] Render имеет `APP_ENV=production`, `INSPECTION_API_KEY` и при
  необходимости `AUTHORIZED_USER_IDS`.
- [ ] Merge в `main` запускает deploy workflow, health-check подтверждает
  здоровую production-версию.
- [ ] Откат проверен на согласованном commit SHA с подтверждением состояния в
  Render и последующим `/health`.
- [ ] Staging повторяет состав prod сервисов и использует отдельные БД и том.
- [ ] Grafana dashboard понятен оператору; метрики, логи и трейсы поступают.
- [ ] Скрипт аномалии вызывает token alert и HTTP 429 на отдельной staging
  базе/пользователе.
- [ ] При baseline без Gemini шестой запрос вызывает alert «Сработали лимиты
  пользователя»; с Gemini пять успешных ответов превышают smoke-test порог
  токенов `> 1` в пятиминутном окне.
- [ ] Compose поднимается на чистой машине.

**Не проверено, нужна проверка человеком:** подключение к Render/GitHub
secrets и реальный production deploy; полный запуск Prometheus/Loki/Tempo/
Grafana и корректность provisioning конкретных версий; поступление живых
трейсов и логов; доставка alert; репетиция rollback; end-to-end anomaly
прогон с PostgreSQL; полноценный Compose startup/inter-container network
в Codespaces (migrate не достиг healthy DB по `db:5432`, хотя миграции и
API/usage прошли через опубликованный порт). В локальном отчёте не выдаются
эти действия за выполненные. Скриншоты Grafana добавляет человек в
`docs/img/`.
