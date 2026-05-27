"""Ollama-backed classification for construction documents (recommendation-only).

The model proposes a classification label + confidence + rationale. The
controller policy (``construction/policy/``) and the deterministic router in
this module decide whether the recommendation is auto-accepted or routed for
manual review. The model never overrides controller validation.
"""

from .client import OllamaChatClient, OllamaUnavailable
from .loader import ModelRoutingError, load_model_routing_config
from .models import (
    PROTECTED_CATEGORIES,
    ClassificationDecision,
    ModelClassification,
    ModelRoutingConfig,
    ModelTaskRouting,
    ProposedLabel,
)
from .router import ClassificationRouter
from .service import ClassificationService
from .validator import InvalidModelOutputError, parse_and_validate

__all__ = [
    "PROTECTED_CATEGORIES",
    "ClassificationDecision",
    "ClassificationRouter",
    "ClassificationService",
    "InvalidModelOutputError",
    "ModelClassification",
    "ModelRoutingConfig",
    "ModelRoutingError",
    "ModelTaskRouting",
    "OllamaChatClient",
    "OllamaUnavailable",
    "ProposedLabel",
    "load_model_routing_config",
    "parse_and_validate",
]
