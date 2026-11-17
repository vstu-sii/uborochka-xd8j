# Monitoring stack

Start the app, PostgreSQL, Prometheus, Loki, Tempo, Alloy and Grafana:

```bash
docker compose -f compose.yml -f monitoring/compose.monitoring.yml up --build
```

Open Grafana at <http://localhost:3000> (`admin` / `change-me` for this
local-only stack), then open the provisioned **Уборочка — Production
overview** dashboard. Prometheus is available at <http://localhost:9090>,
Loki at <http://localhost:3100>, and Tempo at <http://localhost:3200>.
Configure `GRAFANA_ADMIN_PASSWORD` in the shell or an ignored `.env` before
sharing this stack.

The dashboard includes request rate/errors/p95 latency, model calls and token
rates, limit and guard events, and recent Docker logs. The dashboard header
links to Tempo traces. FastAPI spans and the nested `llm.call` span are exported
to Tempo over OTLP gRPC. Prometheus scrapes `/metrics`; Alloy tails Docker JSON
logs and forwards them to Loki.

Grafana provisions a warning when total model-token usage rises above 100,000
tokens in five minutes. To reproduce it locally, configure
`DAILY_REQUEST_LIMIT=5`, `DAILY_TOKEN_LIMIT=5000000`, and
`MONTHLY_BUDGET_USD=10`, then run:

```bash
API_BASE_URL=http://localhost:8000 python scripts/simulate_anomaly.py
```

The script sends five large-but-valid PNG requests followed by one request
expected to receive HTTP 429. The five successful model calls exceed the
100,000-token alert threshold while remaining below the daily token limit.
Use a disposable staging database/user because the usage counters persist for
the current day.

Screenshots: `docs/img/` contains a TODO for a person to capture the dashboard;
no screenshots are claimed as verified here. Starting the Grafana stack and
verifying a live alert were not checked in this environment and need a human
check.
