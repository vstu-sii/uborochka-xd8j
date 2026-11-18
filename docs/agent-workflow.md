# Отчёт DELIVERY по Lab 4

Реализованы production CI/CD с Render Deploy Hook и rollback по SHA,
изолированный staging, мониторинговый стек (Prometheus, Loki, Tempo, Alloy,
Grafana), PostgreSQL-счётчики usage, модельный fallback и application guards.
Проверяемые DoD-пункты и команды собраны в
[docs/lab4-delivery.md](lab4-delivery.md).

В этом рабочем окружении проверялись исходники, unit/API tests, все
Compose-конфигурации и Docker build. Миграции и API с PostgreSQL проверены
через опубликованный порт БД; migrate-контейнер не подключился к healthy DB
по внутренней Docker-сети (TCP timeout), поэтому полный Compose startup
остался не проверен. Реальный деплой на
Render, запуск Grafana-стека, доставка реальных логов/трейсов и репетиция
rollback не проверены, нужна проверка человеком. Все необходимые реальные
значения секретов задаются пользователем в GitHub Secrets и Render; секреты
в репозиторий не добавлялись.
