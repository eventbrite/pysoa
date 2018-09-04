from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import os

import pytest


@pytest.fixture(scope='module')
def server_settings(server_class):
    """
    Load the server_settings used by this service.
    """
    if server_class.use_django:
        from django.conf import settings
    else:
        settings_module = os.environ.get('PYSOA_SETTINGS_MODULE', None)
        assert settings_module, 'PYSOA_SETTINGS_MODULE environment variable must be set to run tests.'
        try:
            settings = importlib.import_module(settings_module)
        except ImportError:
            raise AssertionError('Could not import PYSOA_SETTINGS_MODULE: {}'.format(settings_module))

    try:
        soa_settings = settings.SOA_SERVER_SETTINGS
    except AttributeError:
        try:
            soa_settings = settings.settings
        except AttributeError:
            raise AssertionError('Could not access settings.SOA_SERVER_SETTINGS or settings.settings')
    return soa_settings


@pytest.fixture(scope='module')
def service_client_settings(server_class, server_settings):
    """Config passed to the service client on instantiation"""
    return {
        server_class.service_name: {
            'transport': {
                'path': 'pysoa.common.transport.local:LocalClientTransport',
                'kwargs': {
                    'server_class': server_class,
                    'server_settings': server_settings,
                },
            },
        },
    }


@pytest.fixture(scope='module')
def service_client_class(server_class):
    """
    Override the service client being used to test to automatically inject the service name for
    your testing convenience.
    """
    from pysoa.client import Client  # inline so as not to mess up coverage

    class _TestClient(Client):
        def call_action(self, action, body=None, service_name=None, **kwargs):
            service_name = service_name or server_class.service_name
            return super(_TestClient, self).call_action(service_name, action, body=body, **kwargs)

    return _TestClient


@pytest.fixture(scope='module')
def service_client(service_client_class, service_client_settings):
    """
    Instantiate the service client class with the requisite config. Service doing the testing should define
    the server_class fixture.
    """
    return service_client_class(service_client_settings)


@pytest.fixture
def action_stubber():
    """
    Equivalent of the pytest `mocker` fixture for stub_action, with similar motivations and behavior.
    Allows a test to stub actions without having to manually clean up after the test.
    See https://github.com/pytest-dev/pytest-mock for more info
    """
    from pysoa.test.stub_service import stub_action  # inline so as not to mess up coverage

    stubbies = []

    def _do_stub(*args, **kwargs):
        stubby = stub_action(*args, **kwargs)
        stubbies.append(stubby)
        return stubby.__enter__()

    yield _do_stub

    for stub in stubbies[::-1]:
        stub.__exit__()
