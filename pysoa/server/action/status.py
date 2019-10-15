from __future__ import (
    absolute_import,
    unicode_literals,
)

import abc
import platform
import sys
from typing import (
    Any,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    NamedTuple,
    Optional,
    Tuple,
    Type,
)

import conformity
from conformity import fields
import six

import pysoa
from pysoa.server.action import Action
from pysoa.server.server import Server
from pysoa.server.settings import ServerSettings
from pysoa.server.types import EnrichedActionRequest


__all__ = (
    'BaseStatusAction',
    'CheckMethodReturn',
    'StatusActionFactory',
    'make_default_status_action_class',
)


CheckMethodStatus = NamedTuple(
    'CheckMethodStatus',
    (
        ('is_error', bool),
        ('code', six.text_type),
        ('description', six.text_type),
    ),
)


CheckMethodReturn = Optional[Iterable[CheckMethodStatus]]


class BaseStatusAction(Action):
    """
    Standard base action for status checks. Returns health check and version information.

    If you want to use the status action use `StatusActionFactory(version)`, passing in the version of your service
    and, optionally, the build of your service. If you do not specify an action with name `status` in your server,
    this will be done on your behalf.

    If you want to make a custom status action, subclass this class, make `self._version` return your service's version
    string, `self._build` optionally return your service's build string, and add any additional health check methods
    you desire. Health check methods must start with `check_`.

    Health check methods accept a single argument, the request object (an instance of `ActionRequest`), and return a
    list of tuples in the format `(is_error, code, description)` (or a false-y value if there are no problems):

    - `is_error`: `True` if this is an error, `False` if it is a warning.
    - `code`: Invariant string for this error, like "MYSQL_FAILURE"
    - `description`: Human-readable description of the problem, like "Could not connect to host on port 1234"

    Health check methods can also write to the `self.diagnostics` dictionary to add additional data which will be sent
    back with the response if they like. They are responsible for their own key management in this situation.

    This base status action comes with a disabled-by-default health check method named `_check_client_settings` (the
    leading underscore disables it), which calls `status` on all other services that this service is configured to call
    (using `verbose: False`, which guarantees no further recursive status checking) and includes those responses in
    this action's response. To enable this health check, simply reference it as a new, valid `check_` method name, like
    so:

    .. code:: python

        class MyStatusAction(BaseStatusAction):
            ...
            check_client_settings = BaseStatusAction._check_client_settings
    """

    def __init__(self, settings=None):  # type: (Optional[ServerSettings]) -> None
        """
        Constructs a new base status action. Concrete status actions can override this if they want, but must call
        `super`.

        :param settings: The server settings object
        """
        super(BaseStatusAction, self).__init__(settings)

        self.diagnostics = {}  # type: Dict[six.text_type, Any]

    if six.PY2:
        # noinspection PyDeprecation
        @abc.abstractproperty
        def _version(self):  # type: () -> six.text_type
            """
            Implement this property and return the version string for this service.
            """
    else:
        @property
        @abc.abstractmethod
        def _version(self):  # type: () -> six.text_type
            """
            Implement this property and return the version string for this service.
            """

    @property
    def _build(self):  # type: () -> Optional[six.text_type]
        """
        Optionally override this property and return the full build identifier for this service.
        """
        return None

    description = (
        'Returns version info for the service, Python, PySOA, and Conformity. If the service has a build string, that '
        'is also returned. If the service has defined additional health check behavior and the `verbose` request '
        'attribute is not set to `False`, those additional health checks are performed and returned in the '
        '`healthcheck` response attribute. If the `verbose` request attribute is set to `False`, the additional '
        'health checks are not performed and `healthcheck` is not included in the response (importantly, the `check_` '
        'methods are not invoked).'
    )

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

    def run(self, request):  # type: (EnrichedActionRequest) -> Dict[six.text_type, Any]
        """
        Adds version information for Conformity, PySOA, Python, and the service to the response, then scans the class
        for `check_` methods and runs them (unless `verbose` is `False`).

        :param request: The request object

        :return: The response
        """
        status = {
            'conformity': six.text_type(conformity.__version__),
            'pysoa': six.text_type(pysoa.__version__),
            'python': six.text_type(platform.python_version()),
            'version': self._version,
        }  # type: Dict[six.text_type, Any]

        if self._build:
            status['build'] = self._build

        if not request.body or request.body.get('verbose', True) is True:
            errors = []  # type: List[Tuple[six.text_type, six.text_type]]
            warnings = []  # type: List[Tuple[six.text_type, six.text_type]]
            self.diagnostics = {}

            # Find all things called "check_<something>" on this class.
            # We can't just scan __dict__ because of class inheritance.
            check_methods = (
                getattr(self, x) for x in dir(self) if x.startswith('check_')
            )  # type: Generator[Callable[[EnrichedActionRequest], CheckMethodReturn], None, None]
            for check_method in check_methods:
                # Call the check, and see if it returned anything
                try:
                    problems = check_method(request)
                except TypeError as e:
                    raise RuntimeError(
                        'Status action check_* methods must accept a single argument of type EnrichedActionRequest',
                        e,
                    )
                if problems:
                    try:
                        for is_error, code, description in problems:
                            # Parcel out the values into the right return list
                            if is_error:
                                errors.append((code, description))
                            else:
                                warnings.append((code, description))
                    except (TypeError, ValueError) as e:
                        raise RuntimeError(
                            'Status action check_* methods must return None or an iterable of bool-str-str tuples.',
                            e,
                        )

            status['healthcheck'] = {
                'errors': errors,
                'warnings': warnings,
                'diagnostics': self.diagnostics,
            }

        return status

    def _check_client_settings(self, request):  # type: (EnrichedActionRequest) -> CheckMethodReturn
        """
        This method checks any client settings configured for this service to call other services, calls the `status`
        action of each configured service with `verbose: False` (which guarantees no further recursive status checking),
        adds that diagnostic information, and reports any problems. To include this check in your status action, define
        `check_client_settings = BaseStatusAction._check_client_settings` in your status action class definition.
        """
        if not request.client.settings:
            # There's no need to even add diagnostic details if no client settings are configured
            return None

        self.diagnostics['services'] = {}

        service_names = list(six.iterkeys(request.client.settings))
        try:
            job_responses = request.client.call_jobs_parallel(
                [
                    {'service_name': service_name, 'actions': [{'action': 'status', 'body': {'verbose': False}}]}
                    for service_name in service_names
                ],
                timeout=2,
                catch_transport_errors=True,
                raise_action_errors=False,
                raise_job_errors=False,
            )
        except Exception as e:
            return [CheckMethodStatus(True, 'CHECK_SERVICES_UNKNOWN_ERROR', six.text_type(e))]

        problems = []  # type: List[CheckMethodStatus]
        for i, service_name in enumerate(service_names):
            response = job_responses[i]
            if isinstance(response, Exception):
                problems.append(CheckMethodStatus(
                    True,
                    '{}_TRANSPORT_ERROR'.format(service_name.upper()),
                    six.text_type(response)
                ))
            elif response.errors:
                problems.append(CheckMethodStatus(
                    True,
                    '{}_CALL_ERROR'.format(service_name.upper()),
                    six.text_type(response.errors),
                ))
            elif response.actions[0].errors:
                problems.append(CheckMethodStatus(
                    True,
                    '{}_STATUS_ERROR'.format(service_name.upper()),
                    six.text_type(response.actions[0].errors)
                ))
            else:
                self.diagnostics['services'][service_name] = response.actions[0].body

        return problems


# noinspection PyPep8Naming
def StatusActionFactory(version, build=None, base_class=BaseStatusAction):
    # type: (six.text_type, Optional[six.text_type], Type[BaseStatusAction]) -> Type[BaseStatusAction]
    """
    A factory for creating a new status action class specific to a service.

    :param version: The service version.
    :param build: The optional service build identifier.
    :param base_class: The optional base class, to override `BaseStatusAction` as the base class.

    :return: A class named `StatusAction`, extending `base_class`, with `_version` and `_build` properties returning
             the corresponding `version` and `build` input parameters, respectively.
    """
    class StatusAction(base_class):  # type: ignore
        @property
        def _version(self):  # type: () -> Optional[six.text_type]
            return version

        @property
        def _build(self):  # type: () -> Optional[six.text_type]
            return build

    return StatusAction


def make_default_status_action_class(server_class):  # type: (Type[Server]) -> Type[BaseStatusAction]
    base_module = sys.modules[server_class.__module__.split('.')[0]]

    version = six.text_type(getattr(base_module, '__version__', 'unknown'))
    build = six.text_type(getattr(base_module, '__build__', '')) or None
    return StatusActionFactory(version, build)
