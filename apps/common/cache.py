import hashlib
import logging
import random
import time
from collections.abc import Callable
from functools import partial
from typing import TypeVar
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.core.cache.backends.base import DEFAULT_TIMEOUT
from django.db import transaction
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

T = TypeVar("T")

CACHE_SCHEMA_VERSION = "v1"
MAX_CACHE_KEY_LENGTH = 200
_CACHE_MISS = object()


def jittered_cache_timeout(
    base_timeout: int | None,
    max_jitter_seconds: int,
) -> int | None:
    """Spread cache expirations across a small interval."""
    if base_timeout is None or base_timeout <= 0 or max_jitter_seconds <= 0:
        return base_timeout
    return base_timeout + random.randint(0, max_jitter_seconds)


def build_cache_key(namespace: str, *parts: object) -> str:
    """Build a stable, backend-safe cache key for application data."""
    if not namespace or not namespace.strip():
        raise ValueError("Cache namespace cannot be empty.")

    raw_parts = [CACHE_SCHEMA_VERSION, namespace.strip()]
    raw_parts.extend("none" if part is None else str(part) for part in parts)
    raw_key = ":".join(raw_parts)
    safe_key = ":".join(quote(part, safe="._-") for part in raw_parts)

    if len(safe_key) <= MAX_CACHE_KEY_LENGTH:
        return safe_key

    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()
    return f"{CACHE_SCHEMA_VERSION}:{quote(namespace.strip(), safe='._-')}:{digest}"


def cache_get(key: str, default: T | None = None) -> T | None:
    """Read from cache and degrade to a miss when Redis is unavailable."""
    try:
        return cache.get(key, default)
    except (RedisError, OSError):
        logger.warning("Cache read failed for key %s", key, exc_info=True)
        return default


def cache_set(
    key: str,
    value: object,
    timeout: int | None | object = DEFAULT_TIMEOUT,
) -> bool:
    """Write to cache without turning a Redis outage into an API outage."""
    try:
        cache.set(key, value, timeout=timeout)
        return True
    except (RedisError, OSError):
        logger.warning("Cache write failed for key %s", key, exc_info=True)
        return False


def cache_add(
    key: str,
    value: object,
    timeout: int | None | object = DEFAULT_TIMEOUT,
) -> bool | None:
    try:
        return cache.add(key, value, timeout=timeout)
    except (RedisError, OSError):
        logger.warning("Cache add failed for key %s", key, exc_info=True)
        return None


def cache_delete(*keys: str) -> None:
    if not keys:
        return
    try:
        cache.delete_many(keys)
    except (RedisError, OSError):
        logger.warning("Cache delete failed for keys %s", keys, exc_info=True)


def cache_get_or_set(
    key: str,
    factory: Callable[[], T],
    *,
    timeout: int | None | object = DEFAULT_TIMEOUT,
) -> T:
    cached_value = cache_get(key, _CACHE_MISS)
    if cached_value is not _CACHE_MISS:
        return cached_value

    # ``cache.add`` is atomic in Redis. Only the request that acquires this
    # short-lived marker rebuilds the value; concurrent requests wait briefly
    # for it instead of all executing the same expensive query.
    lock_key = build_cache_key("fill-lock", key)
    lock_timeout = max(1, settings.CACHE_STAMPEDE_LOCK_TIMEOUT)
    acquired = cache_add(lock_key, 1, timeout=lock_timeout)
    if acquired is None:
        value = factory()
        cache_set(key, value, timeout=timeout)
        return value
    if acquired:
        value = factory()
        cache_set(key, value, timeout=timeout)
        # Do not delete the marker: a token-less delete could remove a lock
        # acquired by another request after this one expired. The marker is
        # harmless while the cached value exists and expires quickly.
        return value

    wait_timeout = max(0, settings.CACHE_STAMPEDE_WAIT_TIMEOUT)
    poll_interval = max(0.001, settings.CACHE_STAMPEDE_POLL_INTERVAL)
    deadline = time.monotonic() + wait_timeout
    while time.monotonic() < deadline:
        time.sleep(poll_interval)
        cached_value = cache_get(key, _CACHE_MISS)
        if cached_value is not _CACHE_MISS:
            return cached_value

    # The lock holder may have failed or may simply be slower than the bounded
    # wait. Fall back to the database so Redis can never stall the API.
    value = factory()
    cache_set(key, value, timeout=timeout)
    return value


def invalidate_cache_on_commit(
    callback: Callable[..., object],
    *args: object,
) -> None:
    """Run cache invalidation only after the surrounding DB transaction commits."""
    transaction.on_commit(partial(callback, *args), robust=True)


def cache_is_available() -> bool:
    """Exercise a tiny set/get/delete round-trip for readiness diagnostics."""
    marker = f"{time.monotonic_ns()}"
    key = build_cache_key("health", marker)
    if not cache_set(key, marker, timeout=10):
        return False
    available = cache_get(key) == marker
    cache_delete(key)
    return available


def namespace_generation(namespace: str, *scope: object) -> int:
    key = build_cache_key("generation", namespace, *scope)
    generation = cache_get(key)
    if isinstance(generation, int):
        return generation

    cache_add(key, 1, timeout=None)
    current_generation = cache_get(key, 1)
    return current_generation if isinstance(current_generation, int) else 1


def bump_namespace_generation(namespace: str, *scope: object) -> int:
    key = build_cache_key("generation", namespace, *scope)
    try:
        return cache.incr(key)
    except ValueError:
        cache_set(key, 2, timeout=None)
        return 2
    except (RedisError, OSError):
        logger.warning(
            "Cache generation bump failed for key %s",
            key,
            exc_info=True,
        )
        return 1


def build_versioned_cache_key(
    namespace: str,
    *parts: object,
    scope: tuple[object, ...] = (),
) -> str:
    generation = namespace_generation(namespace, *scope)
    return build_cache_key(namespace, generation, *parts)
