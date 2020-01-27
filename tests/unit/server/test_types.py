from __future__ import (
    absolute_import,
    unicode_literals,
)

import logging

import attr
import pytest

from pysoa.common.errors import Error
from pysoa.common.types import ActionResponse
from pysoa.server.errors import ActionError
from pysoa.server.types import EnrichedActionRequest
from pysoa.test.compatibility import mock


@attr.s
class SuperEnrichedActionRequest(EnrichedActionRequest):
    metrics = attr.ib(default=None)
    analytics_logger = attr.ib(default=None)


class TestEnrichedActionRequest(object):
    def test_call_local_action_no_server(self):
        r = EnrichedActionRequest(action='foo', body={'bar': 'baz'})

        with pytest.raises(ActionError) as error_context:
            r.call_local_action('other_foo', {'color': 'red'})

        assert error_context.value.errors[0].code == 'SERVER_ERROR'

        response = r.call_local_action('other_foo', {'color': 'red'}, raise_action_errors=False)
        assert response.action == 'other_foo'
        assert response.errors
        assert response.errors[0].code == 'SERVER_ERROR'

    def test_call_local_action_no_action(self):
        server = mock.MagicMock()
        server.action_class_map = {'unused_foo': mock.MagicMock()}

        r = EnrichedActionRequest(action='foo', body={'bar': 'baz'})
        r._server = server

        with pytest.raises(ActionError) as error_context:
            r.call_local_action('other_foo', {'color': 'red'})

        assert error_context.value.errors[0].code == 'UNKNOWN'
        assert error_context.value.errors[0].field == 'action'

        response = r.call_local_action('other_foo', {'color': 'red'}, raise_action_errors=False)
        assert response.action == 'other_foo'
        assert response.errors
        assert response.errors[0].code == 'UNKNOWN'
        assert response.errors[0].field == 'action'

    def test_call_local_action_standard_request(self):
        action = mock.MagicMock()
        action.return_value.side_effect = ActionError([Error('FOO', 'Foo error')])

        server = mock.MagicMock()
        server.settings = {'a_setting': 'a_value'}
        server.action_class_map = {'other_foo': action}

        r = EnrichedActionRequest(action='foo', body={'bar': 'baz'})
        r._server = server

        with pytest.raises(ActionError) as error_context:
            r.call_local_action('other_foo', {'color': 'red'})

        assert error_context.value.errors[0].code == 'FOO'

        action.assert_called_once_with(server.settings)
        assert action.return_value.call_count == 1

        other_r = action.return_value.call_args[0][0]
        assert other_r is not r
        assert other_r != r
        assert other_r.action == 'other_foo'
        assert other_r.body == {'color': 'red'}
        assert other_r.context == {}
        assert other_r.control == {}
        assert getattr(other_r, '_server') is server

        action.reset_mock()

        response = r.call_local_action('other_foo', {'color': 'red'}, raise_action_errors=False)
        assert response.action == 'other_foo'
        assert response.errors
        assert response.errors[0].code == 'FOO'

        action.assert_called_once_with(server.settings)
        assert action.return_value.call_count == 1

        other_r = action.return_value.call_args[0][0]
        assert other_r is not r
        assert other_r != r
        assert other_r.action == 'other_foo'
        assert other_r.body == {'color': 'red'}
        assert other_r.context == {}
        assert other_r.control == {}
        assert getattr(other_r, '_server') is server

    def test_call_local_action_other_request_details(self):
        action = mock.MagicMock()
        action.return_value.return_value = ActionResponse(action='another_foo', errors=[Error('BAR', 'Bar error')])

        server = mock.MagicMock()
        server.settings = {'a_setting': 'a_value'}
        server.action_class_map = {'another_foo': action}

        r = EnrichedActionRequest(action='foo', body={'bar': 'baz'}, context={'auth': 'abc123'}, control={'speed': 5})
        r._server = server

        with pytest.raises(ActionError) as error_context:
            r.call_local_action('another_foo', {'height': '10m'})

        assert error_context.value.errors[0].code == 'BAR'

        action.assert_called_once_with(server.settings)
        assert action.return_value.call_count == 1

        other_r = action.return_value.call_args[0][0]
        assert other_r is not r
        assert other_r != r
        assert other_r.action == 'another_foo'
        assert other_r.body == {'height': '10m'}
        assert other_r.context == {'auth': 'abc123'}
        assert other_r.control == {'speed': 5}
        assert getattr(other_r, '_server') is server

        action.reset_mock()

        response = r.call_local_action('another_foo', {'height': '10m'}, raise_action_errors=False)
        assert response.action == 'another_foo'
        assert response.errors
        assert response.errors[0].code == 'BAR'

        action.assert_called_once_with(server.settings)
        assert action.return_value.call_count == 1

        other_r = action.return_value.call_args[0][0]
        assert other_r is not r
        assert other_r != r
        assert other_r.action == 'another_foo'
        assert other_r.body == {'height': '10m'}
        assert other_r.context == {'auth': 'abc123'}
        assert other_r.control == {'speed': 5}
        assert getattr(other_r, '_server') is server

    def test_call_local_action_super_enriched_request(self):
        action = mock.MagicMock()
        action.return_value.return_value = ActionResponse(action='another_foo', body={'sweet': 'success'})

        server = mock.MagicMock()
        server.settings = {'a_setting': 'a_value'}
        server.action_class_map = {'another_foo': action}

        logger = logging.getLogger('test')

        r = SuperEnrichedActionRequest(
            action='foo',
            body={'bar': 'baz'},
            context={'auth_token': 'def456', 'auth': 'original'},
            control={'repeat': True},
            metrics='A custom object',
            analytics_logger=logger,
        )
        r._server = server

        response = r.call_local_action('another_foo', {'entity_id': '1a8t27oh'}, context={'auth': 'new', 'foo': 'bar'})
        assert response.action == 'another_foo'
        assert response.body == {'sweet': 'success'}

        action.assert_called_once_with(server.settings)
        assert action.return_value.call_count == 1

        other_r = action.return_value.call_args[0][0]
        assert isinstance(other_r, SuperEnrichedActionRequest)
        assert other_r is not r
        assert other_r != r
        assert other_r.action == 'another_foo'
        assert other_r.body == {'entity_id': '1a8t27oh'}
        assert other_r.context == {'auth_token': 'def456', 'auth': 'new', 'foo': 'bar'}
        assert other_r.control == {'repeat': True}
        assert other_r.metrics == 'A custom object'
        assert other_r.analytics_logger is logger
        assert getattr(other_r, '_server') is server
