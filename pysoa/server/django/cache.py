from __future__ import absolute_import

from django.core.cache.backends.locmem import LocMemCache
from django.core.cache.backends.memcached import (
    MemcachedCache,
    PyLibMCCache,
)


__all__ = (
    'PySOAMemcachedCache',
    'PySOAProcessScopedMemoryCache',
    'PySOAPyLibMCCache',
    'PySOARequestScopedMemoryCache',
)


class PySOARequestScopedMemoryCache(LocMemCache):
    """
    If you want a request-scoped, in-memory cache that clears at the end of each job request, we recommend you use this
    Django cache engine. You are free to use your own implementation, of course. You can also use this in combination
    with other cache engines (from this module or others) in a multi-cache Django configuration.
    """
    def close(self, **_kwargs):
        """
        Clear the cache completely at the end of each request.
        """
        self.clear()


class PySOAProcessScopedMemoryCache(LocMemCache):
    """
    If you want a server process-scoped, in-memory cache that lasts for the entire server process, we recommend you use
    this Django cache engine. You are free to use your own implementation, of course. You can also use this in
    combination with other cache engines (from this module or others) in a multi-cache Django configuration.
    """
    def close(self, **_kwargs):
        """
        There is no reason to ever clear the cache.
        """


class PySOAMemcachedCache(MemcachedCache):
    """
    If you want to use Memcached with the `python-memcached` library, we recommend you use this Django cache engine,
    which does not close the socket connections to Memcached unless the server is shutting down. You are free to use
    your own implementation, of course. You can also use this in combination with other cache engines (from this module
    or others) in a multi-cache Django configuration.
    """
    def close(self, for_shutdown=False, **_kwargs):
        """
        Only call super().close() if the server is shutting down (not between requests).

        :param for_shutdown: If `False` (the default)
        """
        if for_shutdown:
            super(PySOAMemcachedCache, self).close()


class PySOAPyLibMCCache(PyLibMCCache):
    """
    If you want to use Memcached with the `pylibmc` library, we recommend you use this Django cache engine, which does
    not close the socket connections to Memcached unless the server is shutting down and the super class supports
    closing the connections. You are free to use your own implementation, of course. You can also use this in
    combination with other cache engines (from this module or others) in a multi-cache Django configuration.
    """

    def close(self, for_shutdown=False, **_kwargs):
        """
        Only call super().close() if the server is shutting down (not between requests).

        :param for_shutdown: If `False` (the default)
        """
        if for_shutdown:
            super(PySOAPyLibMCCache, self).close()
