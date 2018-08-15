from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import os

import pytest

from pysoa.client import Client
from pysoa.test.stub_service import stub_action


@pytest.fixture(scope='session')
def server_settings(server_class):
    if server_class.use_django:
        from django.conf import settings
        settings = settings.SOA_SERVER_SETTINGS
    else:
        settings_module = os.environ.get('PYSOA_SETTINGS_MODULE', None)
        assert settings_module, 'PYSOA_SETTINGS_MODULE environment variable must be set to run tests.'
        try:
            thing = importlib.import_module(settings_module)
            settings = thing.SOA_SERVER_SETTINGS
        except (ImportError, AttributeError) as e:
            raise AssertionError('Could not access {}.SOA_SERVER_SETTINGS: {}'.format(settings_module, e))
    return settings


@pytest.fixture(scope='session')
def service_client(server_class, server_settings):
    return Client(
        {
            server_class.service_name: {
                'transport': {
                    'path': 'pysoa.common.transport.local:LocalClientTransport',
                    'kwargs': {
                        'server_class': server_class,
                        'server_settings': server_settings,
                    },
                },
            },
        },
    )


@pytest.fixture(scope='session')
def call_action(server_class, service_client):
    """
    Fixture to call a service action. Defaults to calling the localized service.
    """
    def do_call_action(action, body=None, service_name=None, **kwargs):
        return service_client.call_action(service_name or server_class.service_name, action, body=body, **kwargs)

    return do_call_action


@pytest.fixture
def action_stubber():
    stubbies = []

    def _do_stub(*args, **kwargs):
        stubby = stub_action(*args, **kwargs)
        stubbies.append(stubby)
        return stubby.__enter__()

    yield _do_stub

    for stub in stubbies:
        stub.__exit__()
