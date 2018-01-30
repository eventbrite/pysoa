from __future__ import absolute_import, unicode_literals

import platform

import conformity
from conformity import fields
import six

import pysoa
from pysoa.server.action import Action


class BaseStatusAction(Action):
    """
    Standard base action for status checks.

    Returns heath check and version information.

    If you want to use default StatusAction use StatusActionFactory(version)
    passing in the version of your service.

    If you want to make a custom StatusAction, subclass this class,
    make it get self._version from your service and add additional health check methods.
    Health check methods must start with the word check_.

    Health check methods must take no arguments, and return a list of tuples in the format:
    (is_error, code, description).

    is_error: True if this is an error, False if it is a warning.
    code: Invariant string for this error, like "MYSQL_FAILURE"
    description: Human-readable description of the problem, like "Could not connect to host on port 1234"

    Health check methods can also write to the self.diagnostics dictionary to add additional
    data which will be sent back with the response if they like. They are responsible for their
    own key management in this situation.
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

    request_schema = fields.Dictionary(
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
    )

    response_schema = fields.Dictionary(
        {
            'build': fields.UnicodeString(),
            'conformity': fields.UnicodeString(),
            'healthcheck': fields.Dictionary(
                {
                    'warnings': fields.List(fields.Tuple(fields.UnicodeString(), fields.UnicodeString())),
                    'errors': fields.List(fields.Tuple(fields.UnicodeString(), fields.UnicodeString())),
                    'diagnostics': fields.SchemalessDictionary(key_type=fields.UnicodeString()),
                },
                optional_keys=('warnings', 'errors', 'diagnostics'),
            ),
            'pysoa': fields.UnicodeString(),
            'python': fields.UnicodeString(),
            'version': fields.UnicodeString(),
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

        if request.body.get('verbose', True) is True:
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


if six.PY2:
    def type_str(x):
        return x.encode('utf-8')
else:
    def type_str(x):
        return x


# noinspection PyPep8Naming
def StatusActionFactory(version, build=None, base_class=BaseStatusAction):  # noqa
    return type(
        type_str('StatusAction'),
        (base_class, ),
        {type_str('_version'): version, type_str('_build'): build},
    )
