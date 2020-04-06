from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging


__all__ = (
    'django_close_old_database_connections',
    'django_reset_database_queries',
)


_logger = logging.getLogger(__name__)


try:
    from django.conf import settings
    from django.db import (
        connections as _connections,
        reset_queries as _django_reset_queries,
    )
    from django.db.utils import DatabaseError

    try:
        # noinspection PyPackageRequirements
        from _pytest.outcomes import Failed
    except ImportError:
        class Failed(Exception):  # type: ignore
            pass

    def django_close_old_database_connections():  # type: () -> None
        if getattr(settings, 'DATABASES'):
            _logger.debug('Cleaning Django connections')
            for connection in _connections.all():
                try:
                    if connection.get_autocommit():
                        connection.close_if_unusable_or_obsolete()
                except DatabaseError:
                    # Sometimes old connections won't close because they have already been interrupted (timed out,
                    # server moved, etc.). There's no reason to interrupt server processes for this problem. We can
                    # continue on without issue.
                    pass
                except Failed:
                    # `get_autocommit` fails under PyTest without `pytest.mark.django_db`, so we ignore that specific
                    # error, because this is just a test.
                    pass

    def django_reset_database_queries():  # type: () -> None
        if getattr(settings, 'DATABASES'):
            _logger.debug('Resetting Django query log')
            _django_reset_queries()
except ImportError:
    def django_close_old_database_connections():  # type: () -> None
        pass

    def django_reset_database_queries():  # type: () -> None
        pass
