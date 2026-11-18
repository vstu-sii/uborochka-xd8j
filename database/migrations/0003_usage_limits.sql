BEGIN;

CREATE TABLE IF NOT EXISTS daily_usage (
    user_key       TEXT NOT NULL,
    usage_date     DATE NOT NULL,
    request_count  INTEGER NOT NULL DEFAULT 0 CHECK (request_count >= 0),
    token_count    BIGINT NOT NULL DEFAULT 0 CHECK (token_count >= 0),
    PRIMARY KEY (user_key, usage_date)
);

CREATE TABLE IF NOT EXISTS monthly_usage (
    user_key           TEXT NOT NULL,
    usage_month        DATE NOT NULL,
    estimated_cost_usd NUMERIC(12, 6) NOT NULL DEFAULT 0
                       CHECK (estimated_cost_usd >= 0),
    PRIMARY KEY (user_key, usage_month),
    CHECK (EXTRACT(DAY FROM usage_month) = 1)
);

COMMIT;
