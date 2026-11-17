from prometheus_client import Counter, Histogram

HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "HTTP requests by endpoint and status",
    ["endpoint", "status"],
)
HTTP_ERRORS_TOTAL = Counter(
    "http_errors_total", "HTTP error responses by endpoint", ["endpoint", "status"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency by endpoint",
    ["endpoint"],
)
MODEL_CALLS_TOTAL = Counter(
    "model_calls_total",
    "Model calls by provider, model, and degraded status",
    ["provider", "model", "degraded"],
)
MODEL_TOKENS_TOTAL = Counter(
    "model_tokens_total",
    "Tokens processed by provider and model",
    ["provider", "model"],
)
LIMIT_TRIGGERS_TOTAL = Counter(
    "limit_triggers_total", "User usage limits reached", ["limit"]
)
GUARD_DENIED_TOTAL = Counter(
    "guard_denied_total", "Application guard denials", ["action"]
)
