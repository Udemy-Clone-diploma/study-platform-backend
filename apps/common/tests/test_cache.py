import threading
import time
from unittest.mock import patch

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase, override_settings
from redis.exceptions import ConnectionError

from apps.common.cache import (
    MAX_CACHE_KEY_LENGTH,
    build_cache_key,
    build_versioned_cache_key,
    bump_namespace_generation,
    cache_delete,
    cache_get,
    cache_get_or_set,
    cache_set,
    jittered_cache_timeout,
)
from config import settings as base_settings

TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "common-cache-tests",
    }
}


@override_settings(CACHES=TEST_CACHES)
class CacheHelpersTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_build_cache_key_is_stable_and_escapes_unsafe_characters(self):
        key = build_cache_key("course list", "python & django", None)

        self.assertEqual(
            key,
            "v1:course%20list:python%20%26%20django:none",
        )

    def test_long_cache_key_is_replaced_with_stable_digest(self):
        first = build_cache_key("courses", "x" * 500)
        second = build_cache_key("courses", "x" * 500)

        self.assertEqual(first, second)
        self.assertLessEqual(len(first), MAX_CACHE_KEY_LENGTH)

    def test_cache_get_or_set_reuses_cached_none(self):
        calls = 0

        def factory():
            nonlocal calls
            calls += 1
            return None

        key = build_cache_key("profiles", 10)

        self.assertIsNone(cache_get_or_set(key, factory))
        self.assertIsNone(cache_get_or_set(key, factory))
        self.assertEqual(calls, 1)

    @override_settings(
        CACHE_STAMPEDE_LOCK_TIMEOUT=5,
        CACHE_STAMPEDE_WAIT_TIMEOUT=1,
        CACHE_STAMPEDE_POLL_INTERVAL=0.01,
    )
    def test_concurrent_cache_fill_runs_factory_once(self):
        key = build_cache_key("stampede", "shared")
        factory_started = threading.Event()
        release_factory = threading.Event()
        calls_lock = threading.Lock()
        calls = 0
        results = []

        def factory():
            nonlocal calls
            with calls_lock:
                calls += 1
            factory_started.set()
            release_factory.wait(timeout=1)
            return {"value": 42}

        def load():
            results.append(cache_get_or_set(key, factory, timeout=30))

        first = threading.Thread(target=load)
        first.start()
        self.assertTrue(factory_started.wait(timeout=1))

        second = threading.Thread(target=load)
        second.start()
        time.sleep(0.05)
        release_factory.set()
        first.join(timeout=2)
        second.join(timeout=2)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(calls, 1)
        self.assertEqual(results, [{"value": 42}, {"value": 42}])

    @patch("apps.common.cache.time.sleep")
    @patch("apps.common.cache.cache.set", side_effect=ConnectionError)
    @patch("apps.common.cache.cache.add", side_effect=ConnectionError)
    @patch("apps.common.cache.cache.get", side_effect=ConnectionError)
    def test_redis_failure_does_not_wait_for_fill_lock(
        self,
        _cache_get,
        _cache_add,
        _cache_set,
        sleep,
    ):
        value = cache_get_or_set("unavailable-fill", lambda: "database-value")

        self.assertEqual(value, "database-value")
        sleep.assert_not_called()

    def test_cache_set_get_and_delete(self):
        key = build_cache_key("lessons", 42)

        self.assertTrue(cache_set(key, {"id": 42}))
        self.assertEqual(cache_get(key), {"id": 42})

        cache_delete(key)

        self.assertIsNone(cache_get(key))

    @patch("apps.common.cache.cache.get", side_effect=ConnectionError)
    def test_cache_read_degrades_to_miss_when_redis_is_unavailable(self, _cache_get):
        self.assertEqual(cache_get("unavailable", "fallback"), "fallback")

    def test_bumping_generation_changes_versioned_key(self):
        first = build_versioned_cache_key("courses", "page=1")

        generation = bump_namespace_generation("courses")
        second = build_versioned_cache_key("courses", "page=1")

        self.assertEqual(generation, 2)
        self.assertNotEqual(first, second)

    @patch("apps.common.cache.random.randint", return_value=17)
    def test_jittered_timeout_adds_random_seconds(self, randint):
        timeout = jittered_cache_timeout(300, 60)

        self.assertEqual(timeout, 317)
        randint.assert_called_once_with(0, 60)

    @patch("apps.common.cache.random.randint")
    def test_jittered_timeout_preserves_disabled_or_unbounded_values(self, randint):
        self.assertEqual(jittered_cache_timeout(300, 0), 300)
        self.assertEqual(jittered_cache_timeout(0, 60), 0)
        self.assertIsNone(jittered_cache_timeout(None, 60))
        randint.assert_not_called()


class CacheSettingsTests(SimpleTestCase):
    def test_default_cache_uses_dedicated_redis_backend(self):
        default_cache = base_settings.CACHES["default"]

        self.assertEqual(
            default_cache["BACKEND"],
            "django.core.cache.backends.redis.RedisCache",
        )
        self.assertEqual(default_cache["LOCATION"], settings.CACHE_URL)
        self.assertEqual(default_cache["TIMEOUT"], settings.CACHE_DEFAULT_TIMEOUT)
        self.assertEqual(base_settings.CACHE_TTL_JITTER_SECONDS, 60)
