"""Semantic embedding providers for article similarity scoring.

Supports local Ollama (nomic-embed-text, free) and OpenRouter
(text-embedding-3-small, ~$0.002 per full digest run).

Embeddings are cached in the ``article_embeddings`` table keyed by
(url, model, content_hash) so articles are only re-embedded when their
content changes.
"""

from __future__ import annotations

import logging
import struct
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from condenseit.providers.budget import BudgetTracker
    from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def embed(self, text: str) -> list[float] | None:
        """Return a float embedding vector, or None on failure."""
        ...


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Embedding via a local Ollama instance (zero cost)."""

    def __init__(
        self,
        model: str = "nomic-embed-text",
        host: str = "http://localhost:11434",
    ) -> None:
        self._model = model
        self._host = host.rstrip("/")

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float] | None:
        import httpx

        try:
            resp = httpx.post(
                f"{self._host}/api/embed",
                json={"model": self._model, "input": text[:4000]},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            embeddings = data.get("embeddings") or []
            if embeddings and isinstance(embeddings[0], list):
                return embeddings[0]
        except Exception:
            pass
        # Fallback: older Ollama REST endpoint
        try:
            import httpx

            resp = httpx.post(
                f"{self._host}/api/embeddings",
                json={"model": self._model, "prompt": text[:4000]},
                timeout=60.0,
            )
            resp.raise_for_status()
            data = resp.json()
            emb = data.get("embedding")
            if isinstance(emb, list):
                return emb
        except Exception as exc:
            logger.warning("Ollama embedding failed: %s", exc)
        return None


class OpenRouterEmbeddingProvider(EmbeddingProvider):
    """Embedding via OpenRouter's embeddings endpoint."""

    _ENDPOINT = "https://openrouter.ai/api/v1/embeddings"
    # Fallback price for text-embedding-3-small when OpenRouter does not
    # return a cost field: $0.02 / 1M tokens.
    _PRICE_PER_TOKEN = 2e-8

    def __init__(
        self,
        api_key: str,
        model: str = "openai/text-embedding-3-small",
        budget: BudgetTracker | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._budget = budget

    @property
    def model_name(self) -> str:
        return self._model

    def embed(self, text: str) -> list[float] | None:
        import httpx

        try:
            resp = httpx.post(
                self._ENDPOINT,
                json={"model": self._model, "input": text[:8000]},
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "HTTP-Referer": "https://github.com/condenseit/condenseit",
                    "X-Title": "CondenseIt",
                },
                timeout=30.0,
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("data") or []
            if items and isinstance(items[0].get("embedding"), list):
                if self._budget is not None:
                    usage = data.get("usage") or {}
                    cost = float(usage.get("cost", 0) or 0)
                    total_tokens = int(usage.get("total_tokens", 0) or 0)
                    if cost == 0 and total_tokens > 0:
                        cost = total_tokens * self._PRICE_PER_TOKEN
                    if cost > 0:
                        self._budget.record_spend(
                            cost, model=self._model, tokens=total_tokens
                        )
                return items[0]["embedding"]
        except Exception as exc:
            logger.warning("OpenRouter embedding failed: %s", exc)
        return None


# ---------------------------------------------------------------------------
# Vector storage utilities
# ---------------------------------------------------------------------------


def vec_to_blob(vec: list[float] | np.ndarray) -> bytes:
    """Pack a float vector into a compact bytes blob (float32)."""
    arr = np.asarray(vec, dtype=np.float32)
    n = len(arr)
    return struct.pack(f"{n}f", *arr.tolist())


def blob_to_vec(blob: bytes) -> np.ndarray:
    """Unpack a float32 blob back to a numpy array."""
    n = len(blob) // 4
    return np.array(struct.unpack(f"{n}f", blob), dtype=np.float32)


def cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Return cosine similarity in [-1, 1], or 0.0 when a vector is zero."""
    an = float(np.linalg.norm(a))
    bn = float(np.linalg.norm(b))
    if an < 1e-9 or bn < 1e-9:
        return 0.0
    return float(np.dot(a, b) / (an * bn))


# ---------------------------------------------------------------------------
# Cache-aware embedding lookup
# ---------------------------------------------------------------------------


def get_or_compute_embedding(
    provider: EmbeddingProvider,
    store: ContentStore,
    url: str,
    content_hash: str,
    text: str,
) -> np.ndarray | None:
    """Return a numpy embedding for ``url``, computing and caching if needed.

    Cache key: (url, model, content_hash).  Stale entries (content changed)
    are transparently replaced.
    """
    blob = store.get_embedding(url, provider.model_name, content_hash)
    if blob is not None:
        return blob_to_vec(blob)

    vec = provider.embed(text)
    if vec is None:
        return None

    arr = np.array(vec, dtype=np.float32)
    store.save_embedding(url, provider.model_name, content_hash, vec_to_blob(arr))
    return arr


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def build_embedding_provider(
    embedding_provider: str,
    embedding_model: str,
    ollama_host: str,
    openrouter_api_key: str,
    budget: BudgetTracker | None = None,
) -> EmbeddingProvider | None:
    """Return an EmbeddingProvider or None when the feature is disabled."""
    mode = embedding_provider.lower()
    if mode == "off" or not mode:
        return None
    if mode == "ollama":
        return OllamaEmbeddingProvider(model=embedding_model, host=ollama_host)
    if mode == "openrouter":
        if not openrouter_api_key:
            logger.warning(
                "embedding_provider=openrouter but no API key; embeddings disabled"
            )
            return None
        return OpenRouterEmbeddingProvider(
            api_key=openrouter_api_key, model=embedding_model, budget=budget
        )
    logger.warning("Unknown embedding_provider %r; embeddings disabled", mode)
    return None
