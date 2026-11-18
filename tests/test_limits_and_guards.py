from datetime import date
from decimal import Decimal

import pytest

from backend.guards.actions import GuardDenied, authorize_action, authorize_caller
from backend.limits.service import (
    TOKEN_COST_USD,
    TOKEN_RESERVATION_PER_IMAGE,
    UsageLimitExceeded,
    add_usage_tokens,
    reserve_usage,
    token_usage_ratio,
)


class Cursor:
    def __init__(self, row=None):
        self.row = row

    def fetchone(self):
        return self.row


class MemoryDatabase:
    def __init__(self):
        self.daily = {}
        self.monthly = {}

    def connect(self, *_args, **_kwargs):
        return MemoryConnection(self)


class MemoryConnection:
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def execute(self, query, parameters):
        if "INSERT INTO daily_usage" in query:
            user, period = parameters[:2]
            self.database.daily.setdefault((user, period), [0, 0])
            return Cursor()
        if "INSERT INTO monthly_usage" in query:
            user, period = parameters[:2]
            self.database.monthly.setdefault((user, period), Decimal(0))
            return Cursor()
        if "SELECT request_count, token_count" in query:
            user, period = parameters[:2]
            return Cursor(self.database.daily[(user, period)].copy())
        if "SELECT estimated_cost_usd" in query:
            user, period = parameters[:2]
            return Cursor([self.database.monthly[(user, period)]])
        if "SELECT token_count" in query:
            user, period = parameters[:2]
            value = self.database.daily.get((user, period))
            return Cursor([value[1]] if value else None)
        if "UPDATE daily_usage" in query:
            user = parameters[-2]
            row = self.database.daily[(user, parameters[-1])]
            if "request_count = request_count + 1" in query:
                row[0] += 1
                row[1] += parameters[0]
            else:
                row[1] += parameters[0]
            return Cursor()
        if "UPDATE monthly_usage" in query:
            user = parameters[-2]
            key = (user, parameters[-1])
            self.database.monthly[key] += parameters[0]
            return Cursor()
        raise AssertionError(f"Unrecognized query: {query}")


@pytest.fixture
def usage_db(monkeypatch):
    import backend.limits.service as service

    database = MemoryDatabase()
    monkeypatch.setattr(service.psycopg, "connect", database.connect)
    monkeypatch.setenv("DATABASE_URL", "postgresql://test")
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "2")
    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "20")
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "10")
    return database


def test_daily_request_limit_is_enforced(usage_db):
    today = date(2026, 11, 17)
    reserve_usage("user-1", 1, today=today)
    reserve_usage("user-1", 1, today=today)

    with pytest.raises(UsageLimitExceeded, match="лимит запросов"):
        reserve_usage("user-1", 1, today=today)


def test_daily_token_limit_and_new_day_reset(usage_db):
    first_day = date(2026, 11, 17)
    next_day = date(2026, 11, 18)
    reserve_usage("user-1", 15, today=first_day)

    with pytest.raises(UsageLimitExceeded, match="лимит токенов"):
        reserve_usage("user-1", 6, today=first_day)

    reserve_usage("user-1", 15, today=next_day)
    assert token_usage_ratio("user-1", today=next_day) == 0.75


def test_baseline_usage_reconciles_reservation_to_zero(usage_db, monkeypatch):
    import io

    from PIL import Image

    from backend.providers import BaselineProvider

    monkeypatch.setenv("DAILY_TOKEN_LIMIT", "100000")
    monkeypatch.setenv("MONTHLY_BUDGET_USD", "0")
    today = date(2026, 11, 17)
    photo = io.BytesIO()
    Image.new("RGB", (32, 32), (180, 180, 180)).save(photo, format="PNG")
    assessment = BaselineProvider().analyze(photo.getvalue())
    assert assessment.tokens_used == 0

    reserve_usage("baseline-user", 0, budget_reservation=0, today=today)

    add_usage_tokens(
        "baseline-user",
        0,
        assessment.tokens_used,
        budget_reservation=0,
        today=today,
    )

    assert usage_db.daily[("baseline-user", today)] == [1, 0]
    assert usage_db.monthly[("baseline-user", today.replace(day=1))] == Decimal(0)
    assert TOKEN_COST_USD * usage_db.daily[("baseline-user", today)][1] == Decimal(0)


def test_default_token_limit_accepts_fixed_image_reservation(usage_db, monkeypatch):
    monkeypatch.delenv("DAILY_TOKEN_LIMIT")
    reserve_usage(
        "large-photo-user",
        TOKEN_RESERVATION_PER_IMAGE,
        budget_reservation=TOKEN_RESERVATION_PER_IMAGE,
    )

    assert usage_db.daily[("large-photo-user", date.today())][1] == 1000


def test_guard_allows_only_declared_application_actions():
    authorize_action("assessment.create", user_id="user-1")

    with pytest.raises(GuardDenied):
        authorize_action("database.drop", user_id="user-1")


def test_caller_guard_checks_secret_and_user_allow_list(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("INSPECTION_API_KEY", "local-test-secret")
    monkeypatch.setenv("AUTHORIZED_USER_IDS", "maid-001")

    authorize_caller("local-test-secret", user_id="maid-001")
    with pytest.raises(GuardDenied):
        authorize_caller("wrong", user_id="maid-001")
    with pytest.raises(GuardDenied):
        authorize_caller("local-test-secret", user_id="maid-002")


def test_enabled_gemini_provider_uses_mock_without_network(monkeypatch):
    import backend.providers as providers
    from src.vision.analyze import CleaningAssessment

    calls = []

    class MockGeminiProvider:
        name = "gemini"
        model = "gemini-3.1-flash-lite"

        def __init__(self, api_key):
            assert api_key == "test-key"

        def analyze(self, photo):
            calls.append(photo)
            return CleaningAssessment(8, ["ok"], "high", self.model, False, 9)

    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(providers, "GeminiFlashLiteProvider", MockGeminiProvider)

    assessment, degraded, _, provider = providers.analyze_with_degradation(b"photo")

    assert provider == "gemini"
    assert degraded is False
    assert assessment.tokens_used == 9
    assert calls == [b"photo"]


def test_provider_failure_calls_baseline_fallback(monkeypatch):
    import backend.providers as providers
    from src.vision.analyze import CleaningAssessment

    class FailingGeminiProvider:
        name = "gemini"
        model = "gemini-3.1-flash-lite"

        def __init__(self, api_key):
            pass

        def analyze(self, _photo):
            raise providers.ProviderUnavailable("mocked outage")

    class MockBaselineProvider:
        name = "baseline"
        model = "baseline-heuristic-v1"

        def analyze(self, _photo):
            return CleaningAssessment(7, ["ok"], "medium", self.model, False)

    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    monkeypatch.setattr(providers, "GeminiFlashLiteProvider", FailingGeminiProvider)
    monkeypatch.setattr(providers, "BaselineProvider", MockBaselineProvider)

    assessment, degraded, _, provider = providers.analyze_with_degradation(b"photo")

    assert provider == "baseline"
    assert degraded is True
    assert assessment.degraded is True


def test_enabled_gemini_without_key_fails_explicitly(monkeypatch):
    import backend.providers as providers

    monkeypatch.setenv("GEMINI_ENABLED", "true")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    with pytest.raises(providers.ProviderConfigurationError):
        providers.validate_provider_configuration()


def test_gemini_parses_text_when_sdk_parsed_is_none(monkeypatch):
    import io
    from types import SimpleNamespace

    from google import genai
    from PIL import Image

    from backend.providers import (
        DEFAULT_GEMINI_MODEL,
        GeminiAssessmentSchema,
        GeminiFlashLiteProvider,
    )

    response = SimpleNamespace(
        parsed=None,
        text='{"score": 9, "recommendations": ["Убрано"], "confidence": "high"}',
        usage_metadata=SimpleNamespace(total_token_count=37),
    )
    call = {}

    class Models:
        def generate_content(self, **kwargs):
            call.update(kwargs)
            return response

    class Client:
        def __init__(self, *, api_key):
            assert api_key == "test-key"
            self.models = Models()

    monkeypatch.setattr(genai, "Client", Client)
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    image = io.BytesIO()
    Image.new("RGB", (16, 16), (120, 120, 120)).save(image, format="PNG")

    assessment = GeminiFlashLiteProvider(api_key="test-key").analyze(image.getvalue())

    assert assessment.score == 9
    assert assessment.recommendations == ["Убрано"]
    assert assessment.confidence == "high"
    assert assessment.tokens_used == 37
    assert call["model"] == DEFAULT_GEMINI_MODEL == "gemini-3.1-flash-lite"
    assert call["config"].response_schema is GeminiAssessmentSchema


def test_gemini_model_can_be_configured_from_environment(monkeypatch):
    from backend.providers import GeminiFlashLiteProvider

    monkeypatch.setenv("GEMINI_MODEL", "custom-gemini-model")

    assert GeminiFlashLiteProvider(api_key="test-key").model == "custom-gemini-model"
