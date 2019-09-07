from __future__ import (
    absolute_import,
    unicode_literals,
)

import importlib
import os
from typing import (  # noqa: F401 TODO Python 3
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    Type,
    Union,
    cast,
)
import unittest

from conformity.settings import SettingsData  # noqa: F401 TODO Python 3
import six  # noqa: F401 TODO Python 3

from pysoa.client.client import Client
from pysoa.common.types import (  # noqa: F401 TODO Python 3
    ActionResponse,
    Body,
    Error,
)
from pysoa.server.server import Server
from pysoa.test.assertions import (
    raises_call_action_error,
    raises_error_codes,
    raises_field_errors,
)


class ServerTestCase(unittest.TestCase):
    """
    Base class for test cases that need to call the server.

    It runs calls to actions through the server stack so they get middleware run
    (for things like request.metrics) and requests/responses run through a
    serializer cycle.
    """

    server_class = None  # type: Optional[Type[Server]]
    server_settings = None  # type: Optional[SettingsData]

    def setUp(self):  # type: () -> None
        super(ServerTestCase, self).setUp()

        if self.server_class is None:
            raise TypeError('You must specify `server_class` in `ServerTestCase` subclasses')
        if not issubclass(self.server_class, Server):
            raise TypeError('`server_class` must be a subclass of `Server` in `ServerTestCase` subclasses')
        if not self.server_class.service_name:
            raise TypeError('`server_class.service_name` must be set in `ServerTestCase` subclasses')

        self.service_name = self.server_class.service_name

        # Get settings based on Django mode
        if self.server_settings is not None:
            settings = self.server_settings
        else:
            if self.server_class.use_django:
                from django.conf import settings as django_settings
                settings = cast(SettingsData, django_settings.SOA_SERVER_SETTINGS)  # type: ignore
            else:
                settings_module = os.environ.get('PYSOA_SETTINGS_MODULE', None)
                if not settings_module:
                    self.fail('PYSOA_SETTINGS_MODULE environment variable must be set to run tests.')
                try:
                    thing = importlib.import_module(settings_module)
                    settings = cast(SettingsData, thing.SOA_SERVER_SETTINGS)  # type: ignore
                except (ImportError, AttributeError) as e:
                    self.fail('Could not access {}.SOA_SERVER_SETTINGS: {}'.format(settings_module, e))

        self.client = Client(
            {
                self.service_name: {
                    'transport': {
                        'path': 'pysoa.common.transport.local:LocalClientTransport',
                        'kwargs': {
                            'server_class': self.server_class,
                            'server_settings': settings,
                        },
                    },
                },
            },
        )

    def call_action(self, action, body=None, service_name=None, **kwargs):
        # type: (six.text_type, Body, Optional[six.text_type], **Any) -> ActionResponse
        # Using this enables tests that call the same action dozens of times to not have to code in the service name
        # for every single action call (but they still can by passing in `service_name`)
        return self.client.call_action(service_name or self.service_name, action, body=body, **kwargs)

    def assertActionRunsWithAndReturnErrors(self, action, body, **kwargs):
        # type: (six.text_type, Body, **Any) -> List[Error]
        with raises_call_action_error() as exc_info:
            self.call_action(action, body, **kwargs)
        return exc_info.soa_errors

    def assertActionRunsWithFieldErrors(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        field_errors,  # type: Dict[six.text_type, Union[Iterable[six.text_type], six.text_type]]
        only=False,  # type: bool
        **kwargs  # type: Any
    ):  # type: (...) -> None
        with raises_field_errors(field_errors, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyFieldErrors(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        field_errors,  # type: Dict[six.text_type, Union[Iterable[six.text_type], six.text_type]]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        self.assertActionRunsWithFieldErrors(action, body, field_errors, only=True, **kwargs)

    def assertActionRunsWithErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        only=False,  # type: bool
        **kwargs  # type: Any
    ):  # type: (...) -> None
        with raises_error_codes(error_codes, only=only):
            self.call_action(action, body, **kwargs)

    def assertActionRunsWithOnlyErrorCodes(
        self,
        action,  # type: six.text_type
        body,  # type: Body
        error_codes,  # type: Union[Iterable[six.text_type], six.text_type]
        **kwargs  # type: Any
    ):  # type: (...) -> None
        self.assertActionRunsWithErrorCodes(action, body, error_codes, only=True, **kwargs)
