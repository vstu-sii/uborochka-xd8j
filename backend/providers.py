import io
import os
import time
from dataclasses import dataclass
from typing import Protocol

from opentelemetry import trace
from PIL import Image

from backend.observability import MODEL_CALLS_TOTAL, MODEL_TOKENS_TOTAL
from src.vision.analyze import CleaningAssessment, analyze_photo

tracer = trace.get_tracer(__name__)
FALLBACK_MODEL = "baseline-heuristic-v1"
GEMINI_MODEL = "gemini-2.5-flash-lite"


class ProviderUnavailable(RuntimeError):
    """Raised when an external model provider cannot complete a request."""


class ProviderConfigurationError(RuntimeError):
    """Raised when a configured provider is missing required credentials."""


class ModelProvider(Protocol):
    name: str
    model: str

    def analyze(self, photo: bytes) -> CleaningAssessment: ...


@dataclass
class BaselineProvider:
    name: str = "baseline"
    model: str = FALLBACK_MODEL

    def analyze(self, photo: bytes) -> CleaningAssessment:
        return analyze_photo(photo)


@dataclass
class GeminiFlashLiteProvider:
    api_key: str
    name: str = "gemini"
    model: str = GEMINI_MODEL

    def analyze(self, photo: bytes) -> CleaningAssessment:
        from google import genai
        from google.genai.errors import APIError
        from google.genai import types

        try:
            client = genai.Client(api_key=self.api_key)
            image = Image.open(io.BytesIO(photo))
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    "Оцени чистоту помещения от 1 до 10. Верни JSON: score (int), "
                    "recommendations (array of strings), confidence (low/medium/high).",
                    image,
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                ),
            )
        except APIError as error:
            raise ProviderUnavailable("Gemini request failed") from error
        result = response.parsed
        if not isinstance(result, dict):
            raise ProviderUnavailable("Gemini returned an invalid assessment")
        try:
            score = int(result["score"])
            recommendations = result["recommendations"]
            if not isinstance(recommendations, list):
                raise TypeError("recommendations must be a list")
        except (KeyError, TypeError, ValueError) as error:
            raise ProviderUnavailable(
                "Gemini returned an invalid assessment"
            ) from error
        usage = response.usage_metadata
        return CleaningAssessment(
            score=max(1, min(10, score)),
            recommendations=[str(item) for item in recommendations],
            confidence=str(result.get("confidence", "low")),
            model_used=self.model,
            is_demo=False,
            tokens_used=int(getattr(usage, "total_token_count", 0) or 0),
        )


def analyze_with_degradation(
    photo: bytes, *, use_fallback: bool = False
) -> tuple[CleaningAssessment, bool, float, str]:
    """Call the enabled primary provider or the deterministic Pillow fallback."""
    validate_provider_configuration()
    key = os.getenv("GEMINI_API_KEY")
    enabled = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
    provider: ModelProvider
    degraded = use_fallback
    if use_fallback or not enabled or not key:
        provider = BaselineProvider()
        degraded = use_fallback
    else:
        provider = GeminiFlashLiteProvider(api_key=key)

    request_started = time.perf_counter()
    try:
        assessment, latency = _call_provider(provider, photo, degraded=degraded)
    except ProviderUnavailable:
        if isinstance(provider, BaselineProvider):
            raise
        fallback = BaselineProvider()
        assessment, _ = _call_provider(fallback, photo, degraded=True)
        total_latency = time.perf_counter() - request_started
        return assessment, True, total_latency, fallback.name
    return assessment, degraded, latency, provider.name


def validate_provider_configuration() -> None:
    enabled = os.getenv("GEMINI_ENABLED", "false").lower() == "true"
    if enabled and not os.getenv("GEMINI_API_KEY"):
        raise ProviderConfigurationError(
            "GEMINI_API_KEY is required when GEMINI_ENABLED=true"
        )


def _call_provider(
    provider: ModelProvider, photo: bytes, *, degraded: bool
) -> tuple[CleaningAssessment, float]:
    started = time.perf_counter()
    with tracer.start_as_current_span("llm.call") as span:
        span.set_attribute("provider", provider.name)
        span.set_attribute("model", provider.model)
        try:
            assessment = provider.analyze(photo)
        except ProviderUnavailable:
            latency = time.perf_counter() - started
            span.set_attribute("latency", latency)
            span.set_attribute("tokens", 0)
            span.set_attribute("degraded", True)
            MODEL_CALLS_TOTAL.labels(
                provider=provider.name,
                model=provider.model,
                degraded="true",
            ).inc()
            raise
        latency = time.perf_counter() - started
        tokens = max(0, assessment.tokens_used)
        assessment.tokens_used = tokens
        span.set_attribute("latency", latency)
        span.set_attribute("tokens", tokens)
        span.set_attribute("degraded", degraded)
        assessment.degraded = degraded
        MODEL_CALLS_TOTAL.labels(
            provider=provider.name, model=provider.model, degraded=str(degraded).lower()
        ).inc()
        MODEL_TOKENS_TOTAL.labels(provider=provider.name, model=provider.model).inc(
            tokens
        )
    return assessment, latency
