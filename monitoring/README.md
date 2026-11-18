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

The Prometheus scrape is unauthenticated by default; the application's
`/metrics` endpoint is open unless `METRICS_TOKEN` is set. To enable Bearer
authentication, copy `monitoring/metrics_token.example` to the ignored
`monitoring/metrics_token`, replace its contents with the token, and set the
same value as `METRICS_TOKEN` in the ignored `.env` (or `.env.staging`).
Uncomment the `authorization` block in `monitoring/prometheus.yml` and start
the stack with the optional auth override:

```bash
docker compose -f compose.yml -f monitoring/compose.monitoring.yml \
  -f monitoring/compose.metrics-auth.yml up --build
```

Only this override mounts the local `monitoring/metrics_token` file read-only
at `/etc/prometheus/metrics_token`; the default monitoring stack does not
require that local file. The token is not passed as an environment variable or
written to Prometheus configuration. The example contains comments only.

The dashboard includes request rate/errors/p95 latency, model calls and token
rates, limit and guard events, and recent Docker logs. The dashboard header
links to Tempo traces. FastAPI spans and the nested `llm.call` span are exported
to Tempo over OTLP gRPC. Prometheus scrapes `/metrics`; Alloy tails Docker JSON
logs and forwards them to Loki.
Loki's `trace_id` field links directly to the matching Tempo trace, and
Tempo's trace view can query related logs by trace ID. The dashboard keeps the
Tempo search and recent logs panels side by side.

Grafana provisions two independent alerts:

- **Аномальный расход токенов**: `sum(increase(model_tokens_total[5m])) > 1`.
  This smoke-test threshold is intentionally conservative. Five successful
  Gemini responses with nonzero `usage_metadata.total_token_count` contribute
  at least 1 token apiece: five calls contribute at least 5 in total, so the
  `> 1` threshold is reachable without assuming a fixed image-token cost.
  Raise the smoke-test threshold for production once normal traffic is known.
  For this rule, enable Gemini and provide a valid key.
- **Сработали лимиты пользователя**:
  `sum(increase(limit_triggers_total[5m])) > 0`. Run the script with Gemini
  disabled or no key; the first five baseline-эвристика (Pillow) requests
  succeed and request six returns HTTP 429, incrementing the limit metric.

Configure `DAILY_REQUEST_LIMIT=5`, `DAILY_TOKEN_LIMIT=5000000`, and
`MONTHLY_BUDGET_USD=10`, then run:

```bash
API_BASE_URL=http://localhost:8000 python scripts/simulate_anomaly.py
```

The configured token cap is 5,000,000; five Gemini calls reserve 5 × 1,000 =
5,000 tokens before calls, then reconcile those reservations to the actual
provider-reported token totals. This leaves substantial headroom for the
script's five-call batch; the sixth request is rejected by the request limit
before invoking a provider. Run the batch within five minutes for the rolling
alert window. Use a fresh `MAID_ID` for each run, because request counters
persist per user and day. With baseline and no Gemini key, paid-model tokens
remain zero, but the sixth request still triggers the user-limit alert. If
production auth is enabled, set `INSPECTION_API_KEY` in the process environment
for the script. Use a disposable staging database/user because usage counters
persist for the current day.

Screenshots: `docs/img/` contains a TODO for a person to capture the dashboard;
no screenshots are claimed as verified here. Starting the Grafana stack and
verifying a live alert were not checked in this environment and need a human
check.
