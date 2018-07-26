from __future__ import (
    absolute_import,
    unicode_literals,
)

import re

from conformity import fields
import six

from pysoa.common.constants import ERROR_CODE_INVALID
from pysoa.common.types import Error
from pysoa.server.action.base import Action
from pysoa.server.action.status import BaseStatusAction
from pysoa.server.action.switched import SwitchedAction
from pysoa.server.errors import ActionError
from pysoa.server.internal.types import get_switch
from pysoa.server.server import Server


SWITCHED_ACTION_RE = re.compile(r'^(?P<action>[a-zA-Z0-9_-]+)(\[(switch:(?P<switch>\d+)|(?P<default>DEFAULT))\])$')


class IntrospectionAction(Action):
    """
    This action returns detailed information about the service's defined actions and the request and response schemas
    for each action, along with any documentation defined for the action or for the service itself. It can be passed
    a single action name to return information limited to that single action. Otherwise, it will return information for
    all of the service's actions.

    This action will be added to your service on your behalf if you do not define an action with name `introspect`.

    Making your services and actions capable of being introspected is simple. If your server class has a `description`
    attribute, that will be the service's documentation that introspection returns. If your server class does not have
    this attribute but does have a docstring, introspection will use the docstring. The same rule applies to action
    classes: Introspection first looks for a `description` attribute and then uses the docstring, if any. If neither of
    these are found, the applicable service or action documentation will be done.

    Introspection then looks at the `request_schema` and `response_schema` attributes for each of your actions, and
    includes the details about these schemas in the returned information for each action. Be sure you include field
    descriptions in your schema for the most effective documentation possible.
    """
    description = (
        "This action returns detailed information about the service's defined actions and the request and response "
        "schemas for each action, along with any documentation defined for the action or for the service itself. It "
        "can be passed a single action name to return information limited to that single action. Otherwise, it will "
        "return information for all of the service's actions. If an action is a switched action (meaning the action "
        "extends `SwitchedAction`, and which action code runs is controlled with SOA switches), multiple action "
        "introspection results will be returned for that action, each with a name ending in either `[switch:N]` (where "
        "`N` is the switch value) or `[DEFAULT]` for the default action."
    )

    request_schema = fields.Dictionary(
        {
            'action_name': fields.UnicodeString(
                min_length=1,
                allow_blank=False,
                description='Specify this to limit your introspection to a single action. It will be the only action '
                            'present in the `actions` response attribute. If the requested action does not exist, an '
                            'error will be returned.',
            ),
        },
        optional_keys=('action_name', ),
    )

    response_schema = fields.Dictionary(
        {
            'documentation': fields.Nullable(fields.UnicodeString(
                description='The documentation for the server, unless `action_name` is specified in the request body, '
                            'in which case this is omitted.',
            )),
            'action_names': fields.List(
                fields.UnicodeString(description='The name of an action.'),
                description='An alphabetized list of every action name included in `actions`.',
            ),
            'actions': fields.SchemalessDictionary(
                key_type=fields.UnicodeString(description='The name of the action.'),
                value_type=fields.Dictionary(
                    {
                        'documentation': fields.Nullable(
                            fields.UnicodeString(description='The documentation for the action'),
                        ),
                        'request_schema': fields.Nullable(fields.Anything(
                            description='A description of the expected request schema, including any documentation '
                                        'specified in the schema definition.',
                        )),
                        'response_schema': fields.Nullable(fields.Anything(
                            description='A description of the guaranteed response schema, including any documentation '
                                        'specified in the schema definition.',
                        )),
                    },
                    description='A introspection of a single action',
                ),
                description='A dict mapping action names to action description dictionaries. This contains details '
                            'about every action in the service unless `action_name` is specified in the request body, '
                            'in which case it contains details only for that action.',
            ),
        },
        optional_keys=('documentation', ),
    )

    def __init__(self, server):
        """
        Construct a new introspection action. Unlike its base class, which accepts a server settings object, this
        must be passed a `Server` object, from which it will obtain a settings object. The `Server` code that calls
        this action has special handling to address this requirement.

        :param server: A PySOA server instance
        :type server: Server
        """
        if not isinstance(server, Server):
            raise TypeError('First argument (server) must be a Server instance')

        super(IntrospectionAction, self).__init__(server.settings)

        self.server = server

    def run(self, request):
        """
        Introspects all of the actions on the server and returns their documentation.

        :param request: The request object
        :type request: EnrichedActionRequest

        :return: The response
        """
        if request.body.get('action_name'):
            return self._get_response_for_single_action(request.body.get('action_name'))

        return self._get_response_for_all_actions()

    def _get_response_for_single_action(self, request_action_name):
        action_name = request_action_name
        switch = None

        if SWITCHED_ACTION_RE.match(action_name):
            match = SWITCHED_ACTION_RE.match(action_name)
            action_name = match.group(str('action'))
            if match.group(str('default')):
                switch = SwitchedAction.DEFAULT_ACTION
            else:
                switch = int(match.group(str('switch')))

        if action_name not in self.server.action_class_map and action_name not in ('status', 'introspect'):
            raise ActionError(errors=[
                Error(code=ERROR_CODE_INVALID, message='Action not defined in service', field='action_name'),
            ])

        if action_name in self.server.action_class_map:
            action_class = self.server.action_class_map[action_name]
            if issubclass(action_class, SwitchedAction):
                if switch:
                    if switch == SwitchedAction.DEFAULT_ACTION:
                        action_class = action_class.switch_to_action_map[-1][1]
                    else:
                        for matching_switch, action_class in action_class.switch_to_action_map:
                            if switch == matching_switch:
                                break
                else:
                    response = {
                        'action_names': [],
                        'actions': {}
                    }
                    for sub_name, sub_class in self._iterate_switched_actions(action_name, action_class):
                        response['action_names'].append(sub_name)
                        response['actions'][sub_name] = self._introspect_action(sub_class)
                    response['action_names'] = list(sorted(response['action_names']))
                    return response
        elif action_name == 'introspect':
            action_class = self.__class__
        else:
            action_class = BaseStatusAction

        return {
            'action_names': [request_action_name],
            'actions': {request_action_name: self._introspect_action(action_class)}
        }

    def _get_response_for_all_actions(self):
        response = {
            'actions': {},
            'action_names': [],
            'documentation': getattr(self.server.__class__, 'description', self.server.__class__.__doc__) or None,
        }

        if 'introspect' not in self.server.action_class_map:
            response['action_names'].append('introspect')
            response['actions']['introspect'] = self._introspect_action(self.__class__)

        if 'status' not in self.server.action_class_map:
            response['action_names'].append('status')
            response['actions']['status'] = self._introspect_action(BaseStatusAction)

        for action_name, action_class in six.iteritems(self.server.action_class_map):
            if issubclass(action_class, SwitchedAction):
                for sub_action_name, sub_action_class in self._iterate_switched_actions(action_name, action_class):
                    response['action_names'].append(sub_action_name)
                    response['actions'][sub_action_name] = self._introspect_action(sub_action_class)
            else:
                response['action_names'].append(action_name)
                response['actions'][action_name] = self._introspect_action(action_class)

        response['action_names'] = list(sorted(response['action_names']))

        return response

    @staticmethod
    def _iterate_switched_actions(action_name, action_class):
        found_default = False
        last_index = len(action_class.switch_to_action_map) - 1
        for i, (switch, sub_action_class) in enumerate(action_class.switch_to_action_map):
            if switch == SwitchedAction.DEFAULT_ACTION:
                sub_action_name = '{}[DEFAULT]'.format(action_name)
                found_default = True
            elif not found_default and i == last_index:
                sub_action_name = '{}[DEFAULT]'.format(action_name)
            else:
                sub_action_name = '{}[switch:{}]'.format(action_name, get_switch(switch))

            yield sub_action_name, sub_action_class

    @staticmethod
    def _introspect_action(action_class):
        action = {
            'documentation': getattr(action_class, 'description', action_class.__doc__) or None,
            'request_schema': None,
            'response_schema': None,
        }

        if getattr(action_class, 'request_schema', None):
            action['request_schema'] = action_class.request_schema.introspect()

        if getattr(action_class, 'response_schema', None):
            action['response_schema'] = action_class.response_schema.introspect()

        return action
