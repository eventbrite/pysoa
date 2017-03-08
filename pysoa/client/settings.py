from pysoa.common.settings import SOASettings

from conformity import fields


class ClientSettings(SOASettings):
    """Settings specifically for clients."""
    schema = {
        'cacheable': fields.Boolean(),
    }
    defaults = {
        'cacheable': False,
    }
