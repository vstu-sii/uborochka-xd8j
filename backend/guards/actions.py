import logging
import hmac
import os

from backend.observability import GUARD_DENIED_TOTAL

logger = logging.getLogger(__name__)

ALLOWED_ACTIONS = frozenset({"assessment.create", "recommendation.create"})


class GuardDenied(PermissionError):
    """Raised when an operation is not explicitly allowed by the application."""


def authorize_action(action: str, *, user_id: str | None = None) -> None:
    if action not in ALLOWED_ACTIONS:
        _deny(action, user_id)


def authorize_caller(api_key: str | None, *, user_id: str) -> None:
    expected_key = os.getenv("INSPECTION_API_KEY")
    production = os.getenv("APP_ENV", "development").lower() == "production"
    if production or expected_key:
        if (
            not expected_key
            or not api_key
            or not hmac.compare_digest(api_key.encode(), expected_key.encode())
        ):
            _deny("inspection.call", user_id)

    authorized_users = {
        value.strip()
        for value in os.getenv("AUTHORIZED_USER_IDS", "").split(",")
        if value.strip()
    }
    if authorized_users and user_id not in authorized_users:
        _deny("inspection.call", user_id)


def _deny(action: str, user_id: str | None) -> None:
    GUARD_DENIED_TOTAL.labels(action=action).inc()
    logger.warning(
        "guard_denied",
        extra={"event": "guard_denied", "action": action, "user_id": user_id},
    )
    raise GuardDenied(f"Action is not allowed: {action}")
