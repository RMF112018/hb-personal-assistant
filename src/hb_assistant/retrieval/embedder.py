"""Embedder for retrieval (Phase 11).

Ollama-backed embeddings (preferred for quality, local) with graceful fallback to deterministic
pseudo-embeddings for demo / when Ollama unavailable. Pure python, no extra deps beyond requests.

All texts passed are assumed redacted/bounded excerpts or titles (from prior phases).
Never embed or return full unredacted bodies.
"""

from __future__ import annotations

import hashlib

import requests


class Embedder:
    """Interface for text -> vector."""

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        raise NotImplementedError


class OllamaEmbedder(Embedder):
    """Calls local Ollama /api/embeddings .

    Default model: nomic-embed-text (small, good for semantic on work docs).
    If Ollama not reachable or errors, falls back to deterministic pseudo-vec (dim=64).
    """

    DEFAULT_MODEL = "nomic-embed-text"
    OLLAMA_URL = "http://localhost:11434/api/embeddings"
    FALLBACK_DIM = 64

    def __init__(self, base_url: str | None = None, timeout: float = 10.0):
        self.base_url = base_url or self.OLLAMA_URL
        self.timeout = timeout

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        if not text or not text.strip():
            return [0.0] * self.FALLBACK_DIM
        m = model or self.DEFAULT_MODEL
        try:
            resp = requests.post(
                self.base_url,
                json={"model": m, "prompt": text[:8000]},  # bound input
                timeout=self.timeout,
            )
            resp.raise_for_status()
            data = resp.json()
            vec = data.get("embedding") or data.get("embeddings", [[]])[0]
            if isinstance(vec, list) and len(vec) > 0:
                return [float(x) for x in vec]
        except Exception:
            pass  # fall through to deterministic
        return self._deterministic(text)

    def _deterministic(self, text: str) -> list[float]:
        """Hash-based pseudo embedding for offline/demo (not true semantic, but stable + allows sim code path)."""
        h = hashlib.sha256(text.encode("utf-8", errors="replace")).digest()
        # expand to dim using repeated hash
        dim = self.FALLBACK_DIM
        vec = []
        seed = h
        for i in range(dim):
            seed = hashlib.sha256(seed + bytes([i % 256])).digest()
            val = (int.from_bytes(seed[:4], "big") % 10000) / 10000.0 - 0.5  # -0.5..0.5
            vec.append(val)
        # normalize roughly
        norm = sum(x * x for x in vec) ** 0.5 or 1.0
        return [x / norm for x in vec]


class DeterministicEmbedder(Embedder):
    """Always deterministic (for tests, CI, no net)."""

    def embed(self, text: str, *, model: str | None = None) -> list[float]:
        return OllamaEmbedder()._deterministic(text)
