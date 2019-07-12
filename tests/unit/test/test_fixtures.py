from __future__ import (
    absolute_import,
    unicode_literals,
)

import pytest

from pysoa.server.action import Action
from pysoa.server.server import Server
from pysoa.test.factories import ActionFactory


@pytest.fixture(scope='module')
def server_settings():
    return {}


@pytest.fixture(scope='module')
def test_action():
    class _TestAction(Action):
        def run(self, request):
            return {
                'value': 6,
            }

    return _TestAction


@pytest.fixture(scope='module')
def server_class(test_action):
    class _TestServiceServer(Server):
        service_name = 'test_service'
        action_class_map = {
            'test_action_1': test_action,
            'test_action_2': ActionFactory(body={'value': 1}),
        }

    return _TestServiceServer


def test_localized_service(service_client):
    response = service_client.call_action('test_action_1')

    assert response.body['value'] == 6


def test_action_stubber(service_client, action_stubber):
    action_stubber('test_service', 'test_action_1', body={'value': 7})
    response = service_client.call_action('test_action_1')

    assert response.body['value'] == 7


def test_action_stubber_return_value(service_client, action_stubber):
    stub = action_stubber('test_service', 'test_action_1')
    stub.return_value = {'value': 8}
    response = service_client.call_action('test_action_1')

    assert response.body['value'] == 8


def test_action_stubber_multiple(service_client, action_stubber):
    action_stubber('test_service', 'test_action_1', body={'value': 9})
    action_stubber('test_service', 'test_action_2', body={'value': 10})
    response_1 = service_client.call_action('test_action_1')
    response_2 = service_client.call_action('test_action_2')

    assert response_1.body['value'] == 9
    assert response_2.body['value'] == 10
