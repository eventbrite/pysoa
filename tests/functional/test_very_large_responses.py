from __future__ import (
    absolute_import,
    unicode_literals,
)

import pytest

from pysoa.client.client import Client
from pysoa.common.constants import ERROR_CODE_RESPONSE_TOO_LARGE


def test_very_large_response_protocol_v2(pysoa_client_protocol_v2):  # type: (Client) -> None
    with pytest.raises(pysoa_client_protocol_v2.JobError) as error_context:
        pysoa_client_protocol_v2.call_action('meta', 'very_large_response')

    assert error_context.value.errors[0].code == ERROR_CODE_RESPONSE_TOO_LARGE


def test_very_large_response_default_protocol_v3(pysoa_client):  # type: (Client) -> None
    response = pysoa_client.call_action('meta', 'very_large_response')

    assert response.body == {'key-{}'.format(i): 'value-{}'.format(i) for i in range(10000, 47000)}


def test_very_large_response_json_default_protocol_v3(pysoa_client_json):  # type: (Client) -> None
    response = pysoa_client_json.call_action('meta', 'very_large_response')

    assert response.body == {'key-{}'.format(i): 'value-{}'.format(i) for i in range(10000, 47000)}
