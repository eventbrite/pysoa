from __future__ import (
    absolute_import,
    unicode_literals,
)

import sys
import threading
import time
from typing import Dict

from pysoa.client.client import Client
from pysoa.common.transport.errors import TransientPySOATransportError

from tests.functional import call_command_in_container


def _progress(progress: str) -> None:  # noqa: E999
    sys.stdout.write(progress)
    sys.stdout.flush()


def _new_context() -> Dict:
    return {
        'failover_initiated': False,
        'failover_completed': False,
        'results_before_failover': [],
        'results_after_failover_initiated': [],
        'results_after_failover_completed': [],
        'unexpected_errors_before_failover': [],
        'unexpected_errors_after_failover_initiated': [],
        'unexpected_errors_after_failover_completed': [],
        'stop': False,
        'running': False,
    }


def _work(pysoa_client: Client, service: str, context: Dict) -> None:
    context['running'] = True

    try:
        while context['failover_initiated'] is False and context['stop'] is False:
            try:
                pysoa_client.call_action(service, 'status', {'verbose': False}, timeout=2)
                context['results_before_failover'].append(True)
                _progress('-')
            except TransientPySOATransportError as e:
                context['results_before_failover'].append(e)
                _progress('!')
            except Exception as e:
                context['results_before_failover'].append(e)
                context['unexpected_errors_before_failover'].append(e)
                _progress('¡')
            time.sleep(0.1)

        while context['failover_completed'] is False and context['stop'] is False:
            try:
                pysoa_client.call_action(service, 'status', {'verbose': False}, timeout=2)
                context['results_after_failover_initiated'].append(True)
                _progress('-')
            except TransientPySOATransportError as e:
                context['results_after_failover_initiated'].append(e)
                _progress('!')
            except Exception as e:
                context['results_after_failover_initiated'].append(e)
                context['unexpected_errors_after_failover_initiated'].append(e)
                _progress('¡')
            time.sleep(0.1)

        while context['stop'] is False:
            try:
                pysoa_client.call_action(service, 'status', {'verbose': False}, timeout=2)
                context['results_after_failover_completed'].append(True)
                _progress('-')
            except TransientPySOATransportError as e:
                context['results_after_failover_completed'].append(e)
                _progress('!')
            except Exception as e:
                context['results_after_failover_completed'].append(e)
                context['unexpected_errors_after_failover_completed'].append(e)
                _progress('¡')
            time.sleep(0.1)
    finally:
        context['running'] = False


def _get_master_ip(sentinel_container: str) -> str:
    output = call_command_in_container(
        sentinel_container,
        ['redis-cli', '-p', '26379', 'SENTINEL', 'MASTER', 'functional_tests'],
    )
    next_is_master_ip = False
    for line in output.split('\n'):
        line = line.strip()
        if not line:
            continue

        if next_is_master_ip:
            return line
        if line == 'ip':
            next_is_master_ip = True

    raise AssertionError('Failed parsing master output:\n{}'.format(output))


def _get_redis_role(redis_container: str, authenticate: bool = False, tls: bool = False) -> str:
    args = ['redis-cli', '-p']
    if tls:
        args.extend([
            '46379', '--tls', '--cert', '/usr/local/etc/redis/tls/redis.crt',
            '--key', '/usr/local/etc/redis/tls/redis.key', '--cacert', '/usr/local/etc/redis/tls/ca.crt',
        ])
    else:
        args.append('6379')
    if authenticate:
        args.extend(['--user', 'healthcheck', '--pass', 'KUbMBRRnWxCxLfU4qTaBASCZs467uzxB', '--no-auth-warning'])
    args.append('ROLE')
    output = call_command_in_container(redis_container, args)
    return output.split('\n')[0].strip()


def _initiate_master_failover(sentinel_container: str) -> None:
    output = call_command_in_container(
        sentinel_container,
        ['redis-cli', '-p', '26379', 'SENTINEL', 'FAILOVER', 'functional_tests'],
    )
    assert output == 'OK'


def _kill_master(master_container: str) -> None:
    try:
        # It's weird. Sometimes this command exits 137 to indicate success, sometimes it just returns no output. Either
        # result, apparently, is indicative of success.
        output = call_command_in_container(master_container, ['redis-cli', '-p', '6379', 'SHUTDOWN', 'NOSAVE'])
        assert not output
    except AssertionError as e:
        assert 'Call to docker-compose failed with exit code 137' in e.args[0]


def test_redis5_master_failed_sentinel_failover(pysoa_client: Client) -> None:
    context = _new_context()

    thread = threading.Thread(target=_work, name='test_redis5_planned_demotion', args=(pysoa_client, 'meta', context))
    thread.start()

    try:
        while len(context['results_before_failover']) < 50:
            time.sleep(0.01)
            assert thread.is_alive()

        assert all(r is True for r in context['results_before_failover']), context['results_before_failover']
        assert context['unexpected_errors_before_failover'] == []

        original_master = _get_master_ip('redis5-sentinel1')

        context['failover_initiated'] = True
        _kill_master('redis5-master')
        _progress('/')

        time.sleep(1)
        tries = 0
        new_master = _get_master_ip('redis5-sentinel1')
        while new_master == original_master and tries < 5:
            time.sleep(1)
            tries += 1
            new_master = _get_master_ip('redis5-sentinel1')
        assert new_master != original_master

        tries = 0
        replica1_role = _get_redis_role('redis5-replica1')
        replica2_role = _get_redis_role('redis5-replica2')
        while 'master' not in (replica1_role, replica2_role) and tries < 10:
            time.sleep(1)
            tries += 1
            replica1_role = _get_redis_role('redis5-replica1')
            replica2_role = _get_redis_role('redis5-replica2')
        assert 'master' in (replica1_role, replica2_role)
        context['failover_completed'] = True
        _progress('/')

        assert context['unexpected_errors_after_failover_initiated'] == []

        while len(context['results_after_failover_completed']) < 50:
            time.sleep(0.01)
            assert thread.is_alive()

        context['stop'] = True
        thread.join(6)

        # The last 10 results should have succeeded
        test = context['results_after_failover_completed'][-10:]
        assert all(r is True for r in test), test
        assert context['unexpected_errors_after_failover_completed'] == []

        _progress('//')
    finally:
        context['stop'] = True
        thread.join(6)


def test_redis6_planned_demotion_sentinel_failover(pysoa_client: Client) -> None:
    context = _new_context()

    thread = threading.Thread(target=_work, name='test_redis6_planned_demotion', args=(pysoa_client, 'user', context))
    thread.start()

    try:
        while len(context['results_before_failover']) < 50:
            time.sleep(0.01)
            assert thread.is_alive()

        assert all(r is True for r in context['results_before_failover']), context['results_before_failover']
        assert context['unexpected_errors_before_failover'] == []

        original_master = _get_master_ip('redis6-sentinel1')
        assert _get_redis_role('redis6-master', authenticate=True, tls=True) == 'master'

        context['failover_initiated'] = True
        _initiate_master_failover('redis6-sentinel1')
        _progress('/')

        time.sleep(1)
        tries = 0
        new_master = _get_master_ip('redis6-sentinel1')
        while new_master == original_master and tries < 5:
            time.sleep(1)
            tries += 1
            new_master = _get_master_ip('redis6-sentinel1')
        assert new_master != original_master

        tries = 0
        new_role = _get_redis_role('redis6-master', authenticate=True, tls=True)
        while new_role == 'master' and tries < 10:
            time.sleep(1)
            tries += 1
            new_role = _get_redis_role('redis6-master', authenticate=True, tls=True)
        assert new_role == 'slave'
        context['failover_completed'] = True
        _progress('/')

        assert context['unexpected_errors_after_failover_initiated'] == []

        while len(context['results_after_failover_completed']) < 50:
            time.sleep(0.01)
            assert thread.is_alive()

        context['stop'] = True
        thread.join(6)

        # The last 10 results should have succeeded
        test = context['results_after_failover_completed'][-10:]
        assert all(r is True for r in test), test
        assert context['unexpected_errors_after_failover_completed'] == []

        _progress('//')
    finally:
        context['stop'] = True
        thread.join(6)
