from __future__ import absolute_import, unicode_literals

import platform
import sys

import conformity
from conformity import fields
import six

import pysoa
from pysoa.server.action import Action


class BaseStatusAction(Action):
    """
    Standard base action for status checks.

    Returns health check and version information.

    If you want to use default StatusAction use StatusActionFactory(version), passing in the version of your service.
    If you do not specify an action with name `status` in your server, this will be done on your behalf.

    If you want to make a custom StatusAction, subclass this class, make self._version return your service's version,
    self._build optionally return your service's build string, and add any additional health check methods you desire.
    Health check methods must start with the word check_.

    Health check methods must take no arguments, and return a list of tuples in the format
    `(is_error, code, description)`.

        - is_error: `True` if this is an error, `False` if it is a warning.
        - code: Invariant string for this error, like "MYSQL_FAILURE"
        - description: Human-readable description of the problem, like "Could not connect to host on port 1234"

    Health check methods can also write to the self.diagnostics dictionary to add additional data which will be sent
    back with the response if they like. They are responsible for their own key management in this situation.
    """

    def __init__(self, *args, **kwargs):
        if self.__class__ is BaseStatusAction:
            raise RuntimeError('You cannot use BaseStatusAction directly; it must be subclassed')
        super(BaseStatusAction, self).__init__(*args, **kwargs)

        self.diagnostics = {}

    @property
    def _version(self):
        raise NotImplementedError('version must be defined using StatusActionFactory')

    @property
    def _build(self):
        return None

    description = (
        'Returns version info for the service, Python, PySOA, and Conformity. If the service has a build string, that '
        'is also returned. If the service has defined additional health check behavior and the `verbose` request '
        'attribute is not set to `False`, those additional health checks are performed and returned in the '
        '`healthcheck` response attribute.'
    )

    request_schema = fields.Nullable(fields.Dictionary(
        {
            'verbose': fields.Boolean(
                description='If specified and False, this instructs the status action to return only the baseline '
                            'status information (Python, service, PySOA, and other library versions) and omit any of '
                            'the health check operations (no `healthcheck` attribute will be included in the '
                            'response). This provides a useful way to obtain the service version very quickly without '
                            'executing the often time-consuming code necessary for the full health check. It defaults '
                            'to True, which means "return everything."',
            ),
        },
        optional_keys=('verbose', ),
    ))

    response_schema = fields.Dictionary(
        {
            'build': fields.UnicodeString(description='The version build string, if applicable.'),
            'conformity': fields.UnicodeString(description='The version of Conformity in use.'),
            'healthcheck': fields.Dictionary(
                {
                    'warnings': fields.List(
                        fields.Tuple(
                            fields.UnicodeString(description='The invariant warning code'),
                            fields.UnicodeString(description='The readable warning description'),
                        ),
                        description='A list of any warnings encountered during the health checks.',
                    ),
                    'errors': fields.List(
                        fields.Tuple(
                            fields.UnicodeString(description='The invariant error code'),
                            fields.UnicodeString(description='The readable error description'),
                        ),
                        description='A list of any errors encountered during the health checks.',
                    ),
                    'diagnostics': fields.SchemalessDictionary(
                        key_type=fields.UnicodeString(),
                        description='A dictionary containing any additional diagnostic information output by the '
                                    'health check operations.',
                    ),
                },
                optional_keys=('warnings', 'errors', 'diagnostics'),
                description='Information about any additional health check operations performed.',
            ),
            'pysoa': fields.UnicodeString(description='The version of PySOA in use.'),
            'python': fields.UnicodeString(description='The version of Python in use.'),
            'version': fields.UnicodeString(description='The version of the responding service.'),
        },
        optional_keys=('build', 'healthcheck', ),
    )

    def run(self, request):
        """
        Scans the class for check_ methods and runs them.
        """
        status = {
            'conformity': six.text_type(conformity.__version__),
            'pysoa': six.text_type(pysoa.__version__),
            'python': six.text_type(platform.python_version()),
            'version': self._version,
        }

        if self._build:
            status['build'] = self._build

        if not request.body or request.body.get('verbose', True) is True:
            errors = []
            warnings = []
            self.diagnostics = {}

            # Find all things called "check_<something>" on this class.
            # We can't just scan __dict__ because of class inheritance.
            check_methods = [getattr(self, x) for x in dir(self) if x.startswith('check_')]
            for check_method in check_methods:
                # Call the check, and see if it returned anything
                problems = check_method()
                if problems:
                    for is_error, code, description in problems:
                        # Parcel out the values into the right return list
                        if is_error:
                            errors.append((code, description))
                        else:
                            warnings.append((code, description))

            status['healthcheck'] = {
                'errors': errors,
                'warnings': warnings,
                'diagnostics': self.diagnostics,
            }

        return status


# noinspection PyPep8Naming
def StatusActionFactory(version, build=None, base_class=BaseStatusAction):  # noqa
    return type(
        str('StatusAction'),
        (base_class, ),
        {str('_version'): version, str('_build'): build},
    )


def make_default_status_action_class(server_class):
    base_module = sys.modules[server_class.__module__.split('.')[0]]

    version = six.text_type(getattr(base_module, '__version__', 'unknown'))
    build = six.text_type(getattr(base_module, '__build__', '')) or None
    return StatusActionFactory(version, build)
