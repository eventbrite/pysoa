from pysoa.common.settings import (
    SOASettings,
    class_schema,
)

from conformity import fields


class ClientSettings(SOASettings):
    """Settings specifically for clients."""
    schema = {
        'client': class_schema,
        'cacheable': fields.Boolean(),
    }
    defaults = {
        'client': {'path': u'pysoa.client:Client'},
        'cacheable': False,
    }

    def convert_client(self, value):
        return self.standard_convert_path(value)
