from pysoa.common.settings import BasicClassSchema
from pysoa.common.transport.asgi.constants import ASGI_CHANNEL_TYPES

from conformity import fields


class ASGITransportSchema(BasicClassSchema):
    contents = {
        'path': fields.UnicodeString(),
        'kwargs': fields.Dictionary(
            {
                'asgi_channel_type': fields.Constant(*ASGI_CHANNEL_TYPES),
                'redis_hosts': fields.List(
                    fields.Any(
                        fields.Tuple(fields.UnicodeString(), fields.Integer()),
                        fields.UnicodeString(),
                    )
                ),
                'redis_port': fields.Integer(),
                'sentinel_refresh_interval': fields.Integer(),
                'redis_db': fields.Integer(),
                'sentinel_services': fields.List(fields.UnicodeString()),
                'channel_layer_kwargs': fields.SchemalessDictionary(),
                'channel_full_retries': fields.Integer(),
            },
            optional_keys=[
                'redis_port',
                'sentinel_refresh_interval',
                'redis_db',
                'sentinel_services',
                'channel_layer_kwargs',
                'channel_full_retries',
            ],
            allow_extra_keys=True,
        ),
    }
