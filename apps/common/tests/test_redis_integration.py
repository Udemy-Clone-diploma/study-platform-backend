import os
import time
import uuid
from unittest import skipUnless

from django.core.cache import cache
from django.test import SimpleTestCase, override_settings

from apps.common.cache import (
    build_versioned_cache_key,
    bump_namespace_generation,
    cache_delete,
    cache_get,
    cache_set,
)

RUN_REDIS_TESTS = os.environ.get("REDIS_INTEGRATION_TESTS") == "1"
REDIS_TEST_URL = os.environ.get(
    "REDIS_TEST_CACHE_URL",
    "redis://localhost:6379/15",
)
REDIS_TEST_CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_TEST_URL,
        "KEY_PREFIX": f"redis-integration-{uuid.uuid4().hex}",
        "OPTIONS": {
            "socket_timeout": 2,
            "socket_connect_timeout": 2,
        },
    }
}


@skipUnless(
    RUN_REDIS_TESTS,
    "Set REDIS_INTEGRATION_TESTS=1 to test against a real Redis instance.",
)
@override_settings(CACHES=REDIS_TEST_CACHES)
class RedisBackendIntegrationTests(SimpleTestCase):
    def test_round_trip_and_expiration(self):
        key = f"integration:{uuid.uuid4().hex}"
        self.addCleanup(cache_delete, key)

        self.assertTrue(cache_set(key, {"redis": True}, timeout=1))
        self.assertEqual(cache_get(key), {"redis": True})
        time.sleep(1.1)
        self.assertIsNone(cache_get(key))

    def test_namespace_generation_uses_atomic_redis_increment(self):
        namespace = f"integration-{uuid.uuid4().hex}"
        first = build_versioned_cache_key(namespace, "value")
        generation = bump_namespace_generation(namespace)
        second = build_versioned_cache_key(namespace, "value")

        self.assertEqual(generation, 2)
        self.assertNotEqual(first, second)
