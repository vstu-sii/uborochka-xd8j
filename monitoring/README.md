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
sharing this stack. If `METRICS_TOKEN` is configured for the API, place the
same value in the ignored `.env`; Compose passes it to Prometheus, which
authenticates its `/metrics` scrape with a Bearer token.

The dashboard includes request rate/errors/p95 latency, model calls and token
rates, limit and guard events, and recent Docker logs. The dashboard header
links to Tempo traces. FastAPI spans and the nested `llm.call` span are exported
to Tempo over OTLP gRPC. Prometheus scrapes `/metrics`; Alloy tails Docker JSON
logs and forwards them to Loki.
Loki's `trace_id` field links directly to the matching Tempo trace, and
Tempo's trace view can query related logs by trace ID. The dashboard keeps the
Tempo search and recent logs panels side by side.

Grafana provisions an alert when a paid model reports any tokens in five
minutes (`increase(model_tokens_total[5m]) > 0`). This avoids assuming a fixed
token count for an image: Gemini usage metadata is the source of truth.
The anomaly script succeeds on the first five requests (daily request limit
5) and expects HTTP 429 on request six. For the alert, enable Gemini and provide
its API key; baseline-эвристика (Pillow) reports zero tokens and will not
trigger a paid-model token alert. Configure `DAILY_REQUEST_LIMIT=5`,
`DAILY_TOKEN_LIMIT=5000000`, and `MONTHLY_BUDGET_USD=10`, then run:

```bash
API_BASE_URL=http://localhost:8000 python scripts/simulate_anomaly.py
```

The fixed pre-call reservation is 1,000 tokens per image; after a Gemini call,
it is reconciled to `usage_metadata.total_token_count`. Five typical requests
remain below the 5,000,000-token limit; the sixth is rejected by the request
limit before invoking Gemini. If production auth is enabled, set
`INSPECTION_API_KEY` in the process environment for the script. Use a disposable
staging database/user because the usage counters persist for the current day.

Screenshots: `docs/img/` contains a TODO for a person to capture the dashboard;
no screenshots are claimed as verified here. Starting the Grafana stack and
verifying a live alert were not checked in this environment and need a human
check.
