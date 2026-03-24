"""Vertex AI explicit context cache manager.

Creates and reuses a CachedContent object (system_instruction + tools) per
feature key, so those tokens are not re-billed on every request.

Cost impact:
  - 50 tools schema  ≈ 4,000–5,000 tokens  (billed once per cache TTL)
  - Base system prompt ≈ 1,500–2,500 tokens  (billed once per cache TTL)
  - Per-request input token saving: ~75% discount on cached tokens

Requirements:
  - CONTEXT_CACHING_ENABLED=true in .env
  - MODEL_NAME must be a VERSIONED name, e.g. gemini-2.0-flash-001
    Aliases like "gemini-2.5-flash" are not supported for explicit caching.
"""

import logging
import threading
import time
from dataclasses import dataclass, field

from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600   # 1 hour — Vertex AI cache TTL
_REFRESH_MARGIN = 300        # recreate 5 min before expiry to avoid stale-cache errors


@dataclass
class _CacheEntry:
    name: str
    created_at: float = field(default_factory=time.time)

    def is_fresh(self) -> bool:
        return (time.time() - self.created_at) < (_CACHE_TTL_SECONDS - _REFRESH_MARGIN)


class ContextCacheManager:
    """One Vertex AI context cache per unique (feature_key, system_instruction) pair.

    Caches are created lazily on first use and reused until near-expiry.
    The lock serialises cache creation per feature key so concurrent first
    requests don't create duplicate caches.
    """

    def __init__(self, client: genai.Client, model_name: str, tools: list) -> None:
        self._client = client
        self._model_name = model_name
        self._tools = tools
        self._entries: dict[str | None, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get_cache_name(self, system_instruction: str, feature_key: str | None) -> str | None:
        """Return a valid cache name, creating one if missing or near-expiry.

        Returns None when cache creation fails so the caller falls back to the
        uncached path transparently.
        """
        with self._lock:
            entry = self._entries.get(feature_key)
            if entry is not None and entry.is_fresh():
                return entry.name
            return self._create(system_instruction, feature_key)

    def _create(self, system_instruction: str, feature_key: str | None) -> str | None:
        """Create a new CachedContent. Caller must hold self._lock."""
        try:
            cache = self._client.caches.create(
                model=self._model_name,
                config=types.CreateCachedContentConfig(
                    system_instruction=system_instruction,
                    tools=self._tools,
                    ttl=f"{_CACHE_TTL_SECONDS}s",
                ),
            )
            self._entries[feature_key] = _CacheEntry(name=cache.name)
            logger.info(
                "[ContextCache] Cache created  feature_key=%r  name=%s",
                feature_key, cache.name,
            )
            return cache.name
        except Exception as exc:
            logger.warning(
                "[ContextCache] Cache creation failed for feature_key=%r (%s: %s) "
                "— falling back to uncached path.",
                feature_key, type(exc).__name__, exc,
            )
            return None
