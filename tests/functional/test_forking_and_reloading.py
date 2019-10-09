from __future__ import (
    absolute_import,
    unicode_literals,
)

import time

import pytest

from pysoa.common.constants import ERROR_CODE_ACTION_TIMEOUT
from pysoa.common.transport.errors import MessageReceiveTimeout

from tests.functional import (
    get_container_logs,
    get_container_process_list,
    read_file_from_container,
    write_file_to_container,
)


def test_double_import_trap_killed_intended_service():
    with pytest.raises(AssertionError) as error_context:
        read_file_from_container('echo_service_double_import_trap', '/srv/echo_service-1.heartbeat')

    assert 'No container found for echo_service_double_import_trap_1' in error_context.value.args[0]

    assert 'ERROR: You have triggered a double-import trap' in get_container_logs('echo_service_double_import_trap')


def test_heartbeat_file_watching_no_forking(pysoa_client):
    original_ts = float(read_file_from_container('meta_service', '/srv/meta_service-{{fid}}.heartbeat'))
    assert original_ts > 0
    time.sleep(2.5)

    response = pysoa_client.call_action('meta', 'status')
    assert response.body['version'] == '2.1.7'

    new_ts = float(read_file_from_container('meta_service', '/srv/meta_service-{{fid}}.heartbeat'))
    assert new_ts > original_ts


def test_heartbeat_file_forking_no_watching(pysoa_client):
    original_ts_1 = float(read_file_from_container('user_service', '/srv/user_service-1.heartbeat'))
    original_ts_2 = float(read_file_from_container('user_service', '/srv/user_service-2.heartbeat'))
    original_ts_3 = float(read_file_from_container('user_service', '/srv/user_service-3.heartbeat'))
    original_ts_4 = float(read_file_from_container('user_service', '/srv/user_service-4.heartbeat'))
    assert original_ts_1 > 0
    assert original_ts_2 > 0
    assert original_ts_3 > 0
    assert original_ts_4 > 0
    time.sleep(2.5)

    responses = pysoa_client.call_actions_parallel(
        'user',
        [
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
        ],
    )
    for response in responses:
        assert response.body['version'] == '1.0.17'

    new_ts_1 = float(read_file_from_container('user_service', '/srv/user_service-1.heartbeat'))
    new_ts_2 = float(read_file_from_container('user_service', '/srv/user_service-2.heartbeat'))
    new_ts_3 = float(read_file_from_container('user_service', '/srv/user_service-3.heartbeat'))
    new_ts_4 = float(read_file_from_container('user_service', '/srv/user_service-4.heartbeat'))
    assert new_ts_1 > original_ts_1
    assert new_ts_2 > original_ts_2
    assert new_ts_3 > original_ts_3
    assert new_ts_4 > original_ts_4


def test_heartbeat_file_forking_and_watching(pysoa_client):
    original_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    original_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    original_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert original_ts_1 > 0
    assert original_ts_2 > 0
    assert original_ts_3 > 0
    time.sleep(2.5)

    responses = pysoa_client.call_actions_parallel(
        'echo',
        [
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
        ],
    )
    for response in responses:
        assert response.body['version'] == '9.5.3'

    new_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    new_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    new_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert new_ts_1 > original_ts_1
    assert new_ts_2 > original_ts_2
    assert new_ts_3 > original_ts_3


def test_reload_no_forking(pysoa_client):
    print(get_container_process_list('meta_service'))

    assert read_file_from_container('meta_service', '/srv/meta/meta_service/version.py') == "__version__ = '2.1.7'"

    write_file_to_container('meta_service', '/srv/meta/meta_service/version.py', "__version__ = '7.1.2'")
    assert read_file_from_container('meta_service', '/srv/meta/meta_service/version.py') == "__version__ = '7.1.2'"
    time.sleep(10)

    print(get_container_process_list('meta_service'))

    response = pysoa_client.call_action('meta', 'status')
    assert response.body['version'] == '7.1.2'


def test_reload_with_forking(pysoa_client):
    print(get_container_process_list('echo_service'))

    assert read_file_from_container('echo_service', '/srv/echo/echo_service/version.py') == "__version__ = '9.5.3'"

    write_file_to_container('echo_service', '/srv/echo/echo_service/version.py', "__version__ = '9.8.0'")
    assert read_file_from_container('echo_service', '/srv/echo/echo_service/version.py') == "__version__ = '9.8.0'"
    time.sleep(10)

    print(get_container_process_list('echo_service'))

    responses = pysoa_client.call_actions_parallel(
        'echo',
        [
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
        ],
    )
    for response in responses:
        assert response.body['version'] == '9.8.0'


def test_no_reload_no_watcher(pysoa_client):
    print(get_container_process_list('user_service'))

    assert read_file_from_container('user_service', '/srv/user/user_service/version.py') == "__version__ = '1.0.17'"

    write_file_to_container('user_service', '/srv/user/user_service/version.py', "__version__ = '1.2.1'")
    assert read_file_from_container('user_service', '/srv/user/user_service/version.py') == "__version__ = '1.2.1'"
    time.sleep(10)

    print(get_container_process_list('user_service'))

    responses = pysoa_client.call_actions_parallel(
        'user',
        [
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
            {'action': 'status'}, {'action': 'status'}, {'action': 'status'}, {'action': 'status'},
        ],
    )
    for response in responses:
        assert response.body['version'] == '1.0.17'


def test_harakiri_graceful_restart(pysoa_client):
    original_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    original_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    original_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert original_ts_1 > 0
    assert original_ts_2 > 0
    assert original_ts_3 > 0

    print(get_container_process_list('echo_service'))

    with pytest.raises(pysoa_client.CallActionError) as error_context:
        pysoa_client.call_action('echo', 'harakiri_loop_graceful', timeout=12)

    assert len(error_context.value.actions) == 1
    assert len(error_context.value.actions[0].errors) == 1
    assert error_context.value.actions[0].errors[0].code == ERROR_CODE_ACTION_TIMEOUT

    print(get_container_process_list('echo_service'))

    new_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    new_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    new_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert new_ts_1 > original_ts_1
    assert new_ts_2 > original_ts_2
    assert new_ts_3 > original_ts_3


def test_harakiri_forceful_restart(pysoa_client):
    original_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    original_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    original_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert original_ts_1 > 0
    assert original_ts_2 > 0
    assert original_ts_3 > 0

    print(get_container_process_list('echo_service'))

    with pytest.raises(MessageReceiveTimeout):
        pysoa_client.call_action('echo', 'harakiri_loop_forceful', timeout=12)

    print(get_container_process_list('echo_service'))

    new_ts_1 = float(read_file_from_container('echo_service', '/srv/echo_service-1.heartbeat'))
    new_ts_2 = float(read_file_from_container('echo_service', '/srv/echo_service-2.heartbeat'))
    new_ts_3 = float(read_file_from_container('echo_service', '/srv/echo_service-3.heartbeat'))
    assert new_ts_1 > original_ts_1
    assert new_ts_2 > original_ts_2
    assert new_ts_3 > original_ts_3
