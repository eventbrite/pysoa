from __future__ import (
    absolute_import,
    unicode_literals,
)

import unittest
import warnings

from mockredis import client as mockredis
from mockredis.exceptions import ResponseError
from mockredis.script import Script
import msgpack
import six

from pysoa.common.transport.redis_gateway.backend.standard import StandardRedisClient
from pysoa.test.compatibility import mock


#####
# The following MockRedis fixes were submitted as part of https://github.com/locationlabs/mockredis/pull/133. They can
# be removed once that pull request is merged and a new version of MockRedis is released.
#####

# Patch MockRedis because we don't need CJSON loaded
mockredis.mock_redis_client = lambda *_, **k: mockredis.MockRedis(load_lua_dependencies=False)
mockredis.mock_redis_client.from_url = lambda *_, **k: mockredis.MockRedis(load_lua_dependencies=False)  # type: ignore


def _execute_lua(self, keys, args, client):
    """
    Patch MockRedis+Lua for error_reply
    """
    lua, lua_globals = Script._import_lua(self.load_dependencies)
    lua_globals.KEYS = self._python_to_lua(keys)
    lua_globals.ARGV = self._python_to_lua(args)

    def _call(*call_args):
        # redis-py and native redis commands are mostly compatible argument
        # wise, but some exceptions need to be handled here:
        if str(call_args[0]).lower() == 'lrem':
            response = client.call(
                call_args[0], call_args[1],
                call_args[3],  # "count", default is 0
                call_args[2])
        else:
            response = client.call(*call_args)
        return self._python_to_lua(response)

    def _reply_table(field, message):
        return lua.eval("{{{field}='{message}'}}".format(field=field, message=message))

    lua_globals.redis = {
        'call': _call,
        'status_reply': lambda status: _reply_table('ok', status),
        'error_reply': lambda error: _reply_table('err', error),
    }
    return self._lua_to_python(lua.execute(self.script), return_status=True)


# noinspection PyDecorator
@staticmethod  # type: ignore
def _lua_to_python(lval, return_status=False):
    """
    Patch MockRedis+Lua for Python 3 compatibility
    """
    # noinspection PyUnresolvedReferences
    import lua
    lua_globals = lua.globals()
    if lval is None:
        # Lua None --> Python None
        return None
    if lua_globals.type(lval) == 'table':
        # Lua table --> Python list
        pval = []
        for i in lval:
            if return_status:
                if i == 'ok':
                    return lval[i]
                if i == 'err':
                    raise ResponseError(lval[i])
            pval.append(Script._lua_to_python(lval[i]))
        return pval
    elif isinstance(lval, six.integer_types):
        # Lua number --> Python long
        return six.integer_types[-1](lval)
    elif isinstance(lval, float):
        # Lua number --> Python float
        return float(lval)
    elif lua_globals.type(lval) == 'userdata':
        # Lua userdata --> Python string
        return str(lval)
    elif lua_globals.type(lval) == 'string':
        # Lua string --> Python string
        return lval
    elif lua_globals.type(lval) == 'boolean':
        # Lua boolean --> Python bool
        return bool(lval)
    raise RuntimeError('Invalid Lua type: ' + str(lua_globals.type(lval)))


# noinspection PyDecorator
@staticmethod  # type: ignore
def _python_to_lua(pval):
    """
    Patch MockRedis+Lua for Python 3 compatibility
    """
    # noinspection PyUnresolvedReferences
    import lua
    if pval is None:
        # Python None --> Lua None
        return lua.eval('')
    if isinstance(pval, (list, tuple, set)):
        # Python list --> Lua table
        # e.g.: in lrange
        #     in Python returns: [v1, v2, v3]
        #     in Lua returns: {v1, v2, v3}
        lua_list = lua.eval('{}')
        lua_table = lua.eval('table')
        for item in pval:
            lua_table.insert(lua_list, Script._python_to_lua(item))
        return lua_list
    elif isinstance(pval, dict):
        # Python dict --> Lua dict
        # e.g.: in hgetall
        #     in Python returns: {k1:v1, k2:v2, k3:v3}
        #     in Lua returns: {k1, v1, k2, v2, k3, v3}
        lua_dict = lua.eval('{}')
        lua_table = lua.eval('table')
        for k, v in six.iteritems(pval):
            lua_table.insert(lua_dict, Script._python_to_lua(k))
            lua_table.insert(lua_dict, Script._python_to_lua(v))
        return lua_dict
    elif isinstance(pval, tuple(set(six.string_types + (six.binary_type, )))):  # type: ignore
        # Python string --> Lua userdata
        return pval
    elif isinstance(pval, bool):
        # Python bool--> Lua boolean
        return lua.eval(str(pval).lower())
    elif isinstance(pval, six.integer_types + (float, )):  # type: ignore
        # Python int --> Lua number
        lua_globals = lua.globals()
        return lua_globals.tonumber(str(pval))

    raise RuntimeError('Invalid Python type: ' + str(type(pval)))


# Patch MockRedis for Python 3 compatibility and error_reply
Script._execute_lua = _execute_lua
Script._lua_to_python = _lua_to_python
Script._python_to_lua = _python_to_lua

#####
# End MockRedis fixes
#####


@mock.patch('redis.Redis', new=mockredis.mock_redis_client)
class TestStandardRedisClient(unittest.TestCase):
    @staticmethod
    def _set_up_client(**kwargs):
        return StandardRedisClient(
            hosts=[('169.254.7.12', 6379), ('169.254.8.12', 6379), ('169.254.9.12', 6379)],
            **kwargs
        )

    def test_invalid_hosts(self):
        with self.assertRaises(ValueError):
            StandardRedisClient(hosts='redis://localhost:1234/0')

    def test_simple_send_and_receive(self):
        client = self._set_up_client()

        payload = {'test': 'test_simple_send_receive'}

        client.send_message_to_queue(
            queue_key='test_simple_send_receive',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_simple_send_receive'),
        )

        message = None
        for i in range(3):
            # Message will be on random server
            message = message or client.get_connection('test_simple_send_receive').lpop('test_simple_send_receive')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))

    def test_hashed_server_send_and_receive(self):
        client = self._set_up_client()

        payload1 = {'test': 'some value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload1, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload1, msgpack.unpackb(message, raw=False))

        payload2 = {'for': 'another value'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload2, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload2, msgpack.unpackb(message, raw=False))

        payload3 = {'hashing': 'will this work'}

        client.send_message_to_queue(
            queue_key='test_hashed_send_receive!',
            message=msgpack.packb(payload3, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_hashed_send_receive!'),
        )

        message = client.get_connection('test_hashed_send_receive!').lpop('test_hashed_send_receive!')

        self.assertIsNotNone(message)
        self.assertEqual(payload3, msgpack.unpackb(message, raw=False))

    def test_no_hosts_yields_single_default_host(self):
        client = StandardRedisClient()

        payload = {'test': 'test_no_hosts_yields_single_default_host'}

        client.send_message_to_queue(
            queue_key='test_no_hosts_yields_single_default_host',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_no_hosts_yields_single_default_host'),
        )

        message = client.get_connection(
            'test_no_hosts_yields_single_default_host',
        ).lpop('test_no_hosts_yields_single_default_host')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))

    def test_string_host_yields_single_host(self):
        with warnings.catch_warnings(record=True) as w:
            client = StandardRedisClient(hosts=['redis://localhost:1234/0'])

        assert len(w) == 1
        issubclass(w[0].category, DeprecationWarning)
        assert 'Redis host syntax is deprecated' in str(w[0].message)

        payload = {'test': 'test_string_host_yields_single_host'}

        client.send_message_to_queue(
            queue_key='test_string_host_yields_single_host',
            message=msgpack.packb(payload, use_bin_type=True),
            expiry=10,
            capacity=10,
            connection=client.get_connection('test_string_host_yields_single_host'),
        )

        message = client.get_connection(
            'test_string_host_yields_single_host',
        ).lpop('test_string_host_yields_single_host')

        self.assertIsNotNone(message)
        self.assertEqual(payload, msgpack.unpackb(message, raw=False))
