from __future__ import absolute_import, unicode_literals

from conformity import fields

from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.settings import BasicClassSchema
from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPES


class RedisTransportSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(),
        'kwargs': fields.Dictionary(
            {
                'backend_layer_kwargs': fields.Dictionary(
                    {
                        'connection_kwargs': fields.SchemalessDictionary(
                            description='The arguments used when creating all Redis connections (see Redis-Py docs)',
                        ),
                        'hosts': fields.List(
                            fields.Any(
                                fields.Tuple(fields.UnicodeString(), fields.Integer()),
                                fields.UnicodeString(),
                            ),
                            description='The list of Redis hosts',
                        ),
                        'redis_db': fields.Integer(
                            description='The Redis database, a shortcut for putting this in `connection_kwargs`.',
                        ),
                        'redis_port': fields.Integer(
                            description='The port number, a shortcut for putting this on all hosts',
                        ),
                        'sentinel_refresh_interval': fields.Integer(
                            description='How often (seconds) Redis Sentinel should refresh master info (defaults to '
                                        'every request); should only be used for Sentinel backend type',
                        ),
                        'sentinel_services': fields.List(
                            fields.UnicodeString(),
                            description='A list of Sentinel services (will be discovered by default); should only be '
                                        'used for Sentinel backend type',
                        ),
                    },
                    optional_keys=[
                        'connection_kwargs',
                        'hosts',
                        'redis_db',
                        'redis_port',
                        'sentinel_refresh_interval',
                        'sentinel_services',
                    ],
                    allow_extra_keys=False,
                    description='The arguments passed to the Redis connection manager',
                ),
                'backend_type': fields.Constant(
                    *REDIS_BACKEND_TYPES,
                    description='Which backend (standard or sentinel) should be used for this Redis transport'
                ),
                'message_expiry_in_seconds': fields.Integer(
                    description='How long after a message is sent that it is considered expired, dropped from queue',
                ),
                'queue_capacity': fields.Integer(
                    description='The capacity of the message queue to which this transport will send messages',
                ),
                'queue_full_retries': fields.Integer(
                    description='How many times to retry sending a message to a full queue before giving up',
                ),
                'receive_timeout_in_seconds': fields.Integer(
                    description='How long to block waiting on a message to be received',
                ),
                'serializer_config': BasicClassSchema(
                    object_type=BaseSerializer,
                    description='The configuration for the serializer this transport should use',
                ),
            },
            optional_keys=[
                'backend_layer_kwargs',
                'message_expiry_in_seconds',
                'queue_capacity',
                'queue_full_retries',
                'receive_timeout_in_seconds',
                'serializer_config',
            ],
            allow_extra_keys=False,
        ),
    }
