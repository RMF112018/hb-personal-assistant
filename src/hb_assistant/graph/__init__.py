"""Graph package (Phase 2 base).

Exports GraphHttpClient for centralized, safe, retried calls.
"""

from .http_client import GraphHttpClient

__all__ = ["GraphHttpClient"]
