from __future__ import (
    absolute_import,
    unicode_literals,
)

from conformity import fields

from pysoa.common.serializer.base import Serializer as BaseSerializer
from pysoa.common.transport.redis_gateway.constants import REDIS_BACKEND_TYPES


class RedisTransportSchema(fields.Dictionary):
    contents = {
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
                    description='The list of Redis hosts, where each is a tuple of `("address", port)` or the '
                                'simple string address.',
                ),
                'redis_db': fields.Integer(
                    description='The Redis database, a shortcut for putting this in `connection_kwargs`.',
                ),
                'redis_port': fields.Integer(
                    description='The port number, a shortcut for putting this on all hosts',
                ),
                'sentinel_failover_retries': fields.Integer(
                    description='How many times to retry (with a delay) getting a connection from the Sentinel '
                                'when a master cannot be found (cluster is in the middle of a failover); '
                                'should only be used for Sentinel backend type'
                ),
                'sentinel_services': fields.List(
                    fields.UnicodeString(),
                    description='A list of Sentinel services (will be discovered by default); should only be '
                                'used for Sentinel backend type',
                ),
            },
            optional_keys=(
                'connection_kwargs',
                'hosts',
                'redis_db',
                'redis_port',
                'sentinel_failover_retries',
                'sentinel_services',
            ),
            allow_extra_keys=False,
            description='The arguments passed to the Redis connection manager',
        ),
        'backend_type': fields.Constant(
            *REDIS_BACKEND_TYPES,
            description='Which backend (standard or sentinel) should be used for this Redis transport'
        ),
        'log_messages_larger_than_bytes': fields.Integer(
            description='By default, messages larger than 100KB that do not trigger errors (see '
                        '`maximum_message_size_in_bytes`) will be logged with level WARNING to a logger named '
                        '`pysoa.transport.oversized_message`. To disable this behavior, set this setting to '
                        '0. Or, you can set it to some other number to change the threshold that triggers '
                        'logging.',
        ),
        'maximum_message_size_in_bytes': fields.Integer(
            description='The maximum message size, in bytes, that is permitted to be transmitted over this '
                        'transport (defaults to 100KB on the client and 250KB on the server)',
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
        'default_serializer_config': fields.ClassConfigurationSchema(
            base_class=BaseSerializer,
            description='The configuration for the serializer this transport should use.',
        ),
    }

    optional_keys = (
        'backend_layer_kwargs',
        'log_messages_larger_than_bytes',
        'maximum_message_size_in_bytes',
        'message_expiry_in_seconds',
        'queue_capacity',
        'queue_full_retries',
        'receive_timeout_in_seconds',
        'default_serializer_config',
    )

    description = 'The constructor kwargs for the Redis client and server transports.'
