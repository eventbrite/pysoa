from conformity import fields

from pysoa.common.settings import BasicClassSchema


class ASGITransportSchema(BasicClassSchema):
    contents = {
        'path': BasicClassSchema.contents['path'],
        'kwargs': fields.Dictionary(
            {
                'asgi_channel_type': fields.UnicodeString(),
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
            ]
        ),
    }
