import os
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import psycopg

from backend.observability import LIMIT_TRIGGERS_TOTAL

TOKEN_COST_USD = Decimal("0.0000001")
TOKEN_RESERVATION_PER_IMAGE = 1000


class UsageLimitExceeded(Exception):
    def __init__(self, limit: str, message: str) -> None:
        super().__init__(message)
        self.limit = limit
        self.message = message


class UsageStorageUnavailable(RuntimeError):
    """Raised when the usage database is not configured."""


@dataclass(frozen=True)
class UsageLimits:
    daily_requests: int
    daily_tokens: int
    monthly_budget_usd: Decimal

    @classmethod
    def from_environment(cls) -> "UsageLimits":
        limits = cls(
            daily_requests=int(os.getenv("DAILY_REQUEST_LIMIT", "100")),
            daily_tokens=int(os.getenv("DAILY_TOKEN_LIMIT", "100000")),
            monthly_budget_usd=Decimal(os.getenv("MONTHLY_BUDGET_USD", "10")),
        )
        if (
            limits.daily_requests < 1
            or limits.daily_tokens < 1
            or limits.monthly_budget_usd < 0
        ):
            raise ValueError("Usage limits must be positive (budget may be zero)")
        return limits


def reserve_usage(
    user_key: str,
    estimated_tokens: int,
    *,
    budget_reservation: int = 0,
    today: date | None = None,
) -> None:
    """Atomically reserve one request and estimated provider usage in PostgreSQL."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise UsageStorageUnavailable("DATABASE_URL is not set")

    usage_day = today or date.today()
    usage_month = usage_day.replace(day=1)
    limits = UsageLimits.from_environment()
    estimate = max(0, estimated_tokens)
    reserved_budget_tokens = max(0, budget_reservation)
    cost = TOKEN_COST_USD * reserved_budget_tokens

    with psycopg.connect(database_url) as connection:
        connection.execute(
            """
            INSERT INTO daily_usage (user_key, usage_date)
            VALUES (%s, %s)
            ON CONFLICT (user_key, usage_date) DO NOTHING
            """,
            (user_key, usage_day),
        )
        connection.execute(
            """
            INSERT INTO monthly_usage (user_key, usage_month)
            VALUES (%s, %s)
            ON CONFLICT (user_key, usage_month) DO NOTHING
            """,
            (user_key, usage_month),
        )
        daily = connection.execute(
            """
            SELECT request_count, token_count FROM daily_usage
            WHERE user_key = %s AND usage_date = %s FOR UPDATE
            """,
            (user_key, usage_day),
        ).fetchone()
        monthly = connection.execute(
            """
            SELECT estimated_cost_usd FROM monthly_usage
            WHERE user_key = %s AND usage_month = %s FOR UPDATE
            """,
            (user_key, usage_month),
        ).fetchone()

        if daily[0] >= limits.daily_requests:
            _raise_limit("daily_requests", "Достигнут дневной лимит запросов.")
        if daily[1] + estimate > limits.daily_tokens:
            _raise_limit("daily_tokens", "Достигнут дневной лимит токенов.")
        if monthly[0] + cost > limits.monthly_budget_usd:
            _raise_limit("monthly_budget", "Достигнут месячный бюджет модели.")

        connection.execute(
            """
            UPDATE daily_usage
            SET request_count = request_count + 1, token_count = token_count + %s
            WHERE user_key = %s AND usage_date = %s
            """,
            (estimate, user_key, usage_day),
        )
        connection.execute(
            """
            UPDATE monthly_usage
            SET estimated_cost_usd = estimated_cost_usd + %s
            WHERE user_key = %s AND usage_month = %s
            """,
            (cost, user_key, usage_month),
        )


def add_usage_tokens(
    user_key: str,
    reserved_tokens: int,
    actual_tokens: int,
    *,
    budget_reservation: int = 0,
    today: date | None = None,
) -> None:
    """Replace the per-image reservation with provider-reported token usage."""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise UsageStorageUnavailable("DATABASE_URL is not set")
    usage_day = today or date.today()
    usage_month = usage_day.replace(day=1)
    limits = UsageLimits.from_environment()
    tokens = max(0, actual_tokens)
    reservation = max(0, reserved_tokens)
    delta = tokens - reservation
    reserved_budget_tokens = max(0, budget_reservation)
    cost_delta = TOKEN_COST_USD * (tokens - reserved_budget_tokens)
    limit_exceeded = None

    with psycopg.connect(database_url) as connection:
        daily = connection.execute(
            """
            SELECT token_count FROM daily_usage
            WHERE user_key = %s AND usage_date = %s FOR UPDATE
            """,
            (user_key, usage_day),
        ).fetchone()
        monthly = connection.execute(
            """
            SELECT estimated_cost_usd FROM monthly_usage
            WHERE user_key = %s AND usage_month = %s FOR UPDATE
            """,
            (user_key, usage_month),
        ).fetchone()
        if daily is None or monthly is None:
            raise RuntimeError("Usage reservation must exist before recording tokens")
        if daily[0] + delta > limits.daily_tokens:
            limit_exceeded = (
                "daily_tokens",
                "Достигнут дневной лимит токенов.",
            )
        elif monthly[0] + cost_delta > limits.monthly_budget_usd:
            limit_exceeded = (
                "monthly_budget",
                "Достигнут месячный бюджет модели.",
            )
        connection.execute(
            """
            UPDATE daily_usage SET token_count = token_count + %s
            WHERE user_key = %s AND usage_date = %s
            """,
            (delta, user_key, usage_day),
        )
        connection.execute(
            """
            UPDATE monthly_usage SET estimated_cost_usd = estimated_cost_usd + %s
            WHERE user_key = %s AND usage_month = %s
            """,
            (cost_delta, user_key, usage_month),
        )

    if limit_exceeded:
        _raise_limit(*limit_exceeded)


def token_usage_ratio(user_key: str, *, today: date | None = None) -> float:
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise UsageStorageUnavailable("DATABASE_URL is not set")
    usage_day = today or date.today()
    with psycopg.connect(database_url) as connection:
        row = connection.execute(
            """
            SELECT token_count FROM daily_usage
            WHERE user_key = %s AND usage_date = %s
            """,
            (user_key, usage_day),
        ).fetchone()
    if not row:
        return 0.0
    limit = UsageLimits.from_environment().daily_tokens
    return row[0] / limit if limit > 0 else 1.0


def _raise_limit(limit: str, message: str) -> None:
    LIMIT_TRIGGERS_TOTAL.labels(limit=limit).inc()
    raise UsageLimitExceeded(limit, message)
