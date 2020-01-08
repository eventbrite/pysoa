from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import os
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Optional,
    Type,
    Union,
    cast,
)

from conformity.settings import SettingsData
import pytest
import six

from pysoa.client.client import Client
from pysoa.common.transport.local import LocalClientTransport
from pysoa.common.types import (
    ActionResponse,
    Body,
)
from pysoa.server.errors import ActionError
from pysoa.server.server import Server
from pysoa.test.compatibility import mock
from pysoa.test.stub_service import (
    Errors,
    stub_action,
)


@pytest.fixture(scope='module')
def server_settings(server_class):  # type: (Type[Server]) -> SettingsData
    """
    Load the server_settings used by this service.
    """
    if server_class.use_django:
        # noinspection PyUnresolvedReferences
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
    return cast(SettingsData, soa_settings)


@pytest.fixture(scope='module')
def service_client_settings(server_class, server_settings):
    # type: (Type[Server], SettingsData) -> Dict[six.text_type, SettingsData]
    """Config passed to the service client on instantiation"""
    assert server_class.service_name
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
    # type: (Type[Server]) -> Type[Client]
    """
    Override the service client being used to test to automatically inject the service name for
    your testing convenience.
    """

    assert server_class.service_name
    _service_name = server_class.service_name

    class _TestClient(Client):
        def call_action(  # type: ignore # to ignore 'Signature of "call_action" is incompatible with supertype' error
            self,
            action,
            body=None,
            service_name=None,
            **kwargs
        ):
            # type: (six.text_type, Optional[Body], Optional[six.text_type], **Any) -> ActionResponse # type: ignore
            service_name = service_name or _service_name
            return super(_TestClient, self).call_action(service_name, action, body=body, **kwargs)

    return _TestClient


@pytest.fixture(scope='module')
def service_client(server_class, service_client_class, service_client_settings):
    # type: (Type[Server], Type[Client], Dict[six.text_type, SettingsData]) -> Client
    """
    Instantiate the service client class with the requisite config. Service doing the testing should define
    the server_class fixture.
    """
    assert server_class.service_name

    client = service_client_class(service_client_settings)
    # noinspection PyProtectedMember
    cast(
        LocalClientTransport,
        client._get_handler(server_class.service_name).transport,
    ).server._skip_django_database_cleanup = True
    return client


_StubActionSignature = Callable[
    [
        six.text_type,
        six.text_type,
        Optional[Body],
        Optional[Errors],
        Optional[Union[Body, ActionError, Callable[[Body], Body]]],
    ],
    mock.MagicMock,
]


@pytest.fixture
def action_stubber():
    # type: () -> Generator[_StubActionSignature, None, None]
    """
    Equivalent of the pytest `mocker` fixture for stub_action, with similar motivations and behavior.
    Allows a test to stub actions without having to manually clean up after the test.
    See https://github.com/pytest-dev/pytest-mock for more info
    """

    stubbies = []

    def _do_stub(
        service,  # type: six.text_type
        action,  # type: six.text_type
        body=None,  # type: Optional[Body]
        errors=None,  # type: Optional[Errors]
        side_effect=None,  # type: Optional[Union[Body, ActionError, Callable[[Body], Body]]]
    ):  # type: (...) -> mock.MagicMock
        stubby = stub_action(service, action, body, errors, side_effect)  # type: stub_action
        stubbies.append(stubby)
        return stubby.__enter__()

    yield _do_stub

    for stub in stubbies[::-1]:
        stub.__exit__()
