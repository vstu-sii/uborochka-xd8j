# Environments

| Параметр | local | staging | prod |
|---|---|---|---|
| URL | `http://localhost:8000` | `http://localhost:8001` | `https://uborochka-xd8j.onrender.com` |
| БД | `uborochka` | `uborochka_staging` | Render PostgreSQL (`DATABASE_URL`) |
| Порты | API `8000`, PostgreSQL `5432` | API `8001`, PostgreSQL `5433` | Render HTTPS; database private URL |
| Лимиты (по умолчанию) | 100 запросов / 100 000 токенов в день, $10/месяц | те же, можно задать отдельно | задаются Render env vars |
| Авторизация | API key не обязателен локально | API key включается при задании `INSPECTION_API_KEY` | `APP_ENV=production` требует `INSPECTION_API_KEY` |
| Провайдер модели | baseline-эвристика (Pillow); Gemini выключен | baseline-эвристика (Pillow); Gemini выключен | baseline-эвристика (Pillow), Gemini опционально |
| Уровень логов | `INFO` | `INFO` | `INFO` (Render env) |

`/metrics` остаётся открытым, когда `METRICS_TOKEN` не задан. Для защищённого
endpoint задайте один и тот же `METRICS_TOKEN` приложению и Prometheus в
локальном `.env`, staging env или Render. Prometheus передаёт значение как
`Authorization: Bearer ...`; не добавляйте токен в конфигурационные файлы или
логи.

Staging повторяет локальный Compose и production Docker image; отличаются
только `APP_ENV`/`ENVIRONMENT`, имена БД и тома, внешние порты, а также конфигурация
секретов и ресурсов. Отдельная БД и именованный том не дают тестовым
миграциям и данным пересечься с локальными или производственными. Лимиты
staging следует выбирать так, чтобы проверять ограничения без влияния на
production. Токены для базовой эвристики оцениваются по размеру входных
данных; для платного провайдера цена месячного бюджета также является
приближённой по ставке `0.10 USD / 1M` токенов.

## Запуск staging на чистой машине

Нужны Docker Engine и Docker Compose v2. Секреты не требуются при выключенном
Gemini. Для собственного набора параметров создайте `.env.staging` из
`.env.staging.example`; этот файл игнорируется Git.

```bash
cp .env.staging.example .env.staging
docker compose -f compose.yml -f compose.staging.yml up --build
```

API: <http://localhost:8001>, health: <http://localhost:8001/health>,
PostgreSQL опубликован на `localhost:5433`. Для остановки:
`docker compose -f compose.yml -f compose.staging.yml down`.
Для удаления staging-данных отдельно удалите named volume `pgdata_staging`
после проверки его имени; не удаляйте volume production.

Compose configuration syntax is checked with:

```bash
docker compose config
docker compose -f compose.yml -f compose.staging.yml config
```

Фактический запуск staging в Codespaces был попытан, но migrate-контейнер не
смог подключиться к healthy PostgreSQL по внутреннему адресу `db:5432`
(TCP timeout — сетевое ограничение среды). Через опубликованный порт 5433
миграции повторно применились, `/health`, `POST /inspection`, запись usage
в PostgreSQL и `/metrics` прошли проверку из host-процесса. Поэтому
конфигурация и интеграция с БД проверены, но запуск Compose-сервисов и
межконтейнерная сеть в этой среде не проверены; нужна проверка человеком на
чистой машине.
