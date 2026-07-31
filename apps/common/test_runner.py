import unittest

from django.core.cache import caches
from django.test.runner import DiscoverRunner


class CacheClearingTextTestResult(unittest.TextTestResult):
    """Keep shared cache state from leaking between database-isolated tests."""

    def startTest(self, test):
        for cache_backend in caches.all():
            cache_backend.clear()
        super().startTest(test)


class CacheClearingTextTestRunner(unittest.TextTestRunner):
    resultclass = CacheClearingTextTestResult


class CacheIsolatedDiscoverRunner(DiscoverRunner):
    test_runner = CacheClearingTextTestRunner
