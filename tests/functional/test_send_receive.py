from __future__ import (
    absolute_import,
    unicode_literals,
)

from pysoa.client.client import Client


def test_send_receive_redis5_redis6_round_robin(pysoa_client: Client):  # noqa: E999
    for i in range(10):
        response = pysoa_client.call_action('echo', 'status', body={'verbose': False})
        assert response.body, 'Iteration {} failed'.format(i)


def test_send_receive_redis5(pysoa_client: Client):
    response = pysoa_client.call_action('meta', 'status', body={'verbose': False})
    assert response.body


def test_send_receive_redis6_auth_and_ssl(pysoa_client: Client):
    response = pysoa_client.call_action('user', 'status', body={'verbose': False})
    assert response.body
