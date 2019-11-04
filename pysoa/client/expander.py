from __future__ import (
    absolute_import,
    unicode_literals,
)

from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
    cast,
)

from conformity import fields
from conformity.settings import (
    Settings,
    SettingsSchema,
)
import six


__all__ = (
    'ExpansionConverter',
    'ExpansionNode',
    'Expansions',
    'ExpansionSettings',
    'TypeExpansions',
    'TypeNode',
    'TypeRoutes',
)


class ExpansionSettings(Settings):
    """
    Defines the schema for configuration settings used when expanding objects on responses with the Expansions tool.
    """

    schema = {
        'type_routes': fields.SchemalessDictionary(
            key_type=fields.UnicodeString(
                description='The name of the expansion route, to be referenced from the `type_expansions` '
                            'configuration',
            ),
            value_type=fields.Dictionary(
                {
                    'service': fields.UnicodeString(
                        description='The name of the service to call to resolve this route',
                    ),
                    'action': fields.UnicodeString(
                        description='The name of the action to call to resolve this route, which must accept a single '
                                    'request field of type `List`, to which all the identifiers for matching candidate '
                                    'expansions will be passed, and which must return a single response field of type '
                                    '`Dictionary`, from which all expansion objects will be obtained',
                    ),
                    'request_field': fields.UnicodeString(
                        description='The name of the `List` identifier field to place in the `ActionRequest` body when '
                                    'making the request to the named service and action',
                    ),
                    'response_field': fields.UnicodeString(
                        description='The name of the `Dictionary` field returned in the `ActionResponse`, from which '
                                    'the expanded objects will be extracted',
                    ),
                },
                description='The instructions for resolving this type route',
            ),
            description='The definition of all recognized types that can be expanded into and information about how '
                        'to resolve objects of those types through action calls',
        ),
        'type_expansions': fields.SchemalessDictionary(
            key_type=fields.UnicodeString(
                description='The name of the type for which the herein defined expansions can be sought, which will be '
                            "matched with a key from the `expansions` dict passed to one of `Client`'s `call_***` "
                            'methods, and which must also match the value of a `_type` field found on response objects '
                            'on which extra data will be expanded',
            ),
            value_type=fields.SchemalessDictionary(
                key_type=fields.UnicodeString(
                    description='The name of an expansion, which will be matched with a value from the `expansions` '
                                "dict passed to one of `Client`'s `call_***` methods corresponding to the type key in "
                                'that dict',
                ),
                value_type=fields.Dictionary(
                    {
                        'type': fields.Nullable(fields.UnicodeString(
                            description='The type of object this expansion yields, which must map back to a '
                                        '`type_expansions` key in order to support nested/recursive expansions, and '
                                        'may be `None` if you do not wish to support nested/recursive expansions for '
                                        'this expansion',
                        )),
                        'route': fields.UnicodeString(
                            description='The route to use to resolve this expansion, which must match a key in the '
                                        '`type_routes` configuration',
                        ),
                        'source_field': fields.UnicodeString(
                            description='The name of the field in the base object that contains the identifier used '
                                        'for obtaining the expansion object (the identifier will be passed to the '
                                        '`request_field` in the route when resolving the expansion)',
                        ),
                        'destination_field': fields.UnicodeString(
                            description='The name of a not-already-existent field in the base object into which the '
                                        'expansion object will be placed after it is obtained from the route',
                        ),
                        'raise_action_errors': fields.Boolean(
                            description='Whether to raise action errors encountered when expanding objects these '
                                        'objects (by default, action errors are suppressed, which differs from the '
                                        'behavior of the `Client` to raise action errors during normal requests)',
                        ),
                    },
                    optional_keys=('raise_action_errors', ),
                    description='The definition of one specific possible expansion for this object type',
                ),
                description='The definition of all possible expansions for this object type',
            ),
            description='The definition of all types that may contain identifiers that can be expanded into objects '
                        'using the `type_routes` configurations',
        ),
    }  # type: SettingsSchema


class TypeNode(object):
    """
    Represents a type node for an expansion tree.
    """

    def __init__(self, node_type):  # type: (six.text_type) -> None
        """
        Create a new `TypeNode` instance.

        :param node_type: The node type name
        """
        self.type = node_type
        self._expansions = {}  # type: Dict[six.text_type, ExpansionNode]

    def add_expansion(self, expansion_node):  # type: (ExpansionNode) -> None
        """
        Add a child expansion node to the type node's expansions.

        If an expansion node with the same name is already present in type node's expansions, the new and existing
        expansion node's children are merged.

        :param expansion_node: The expansion node to add
        """
        # Check for existing expansion node with the same name
        existing_expansion_node = self.get_expansion(expansion_node.name)  # type: Optional[ExpansionNode]
        if existing_expansion_node:
            # Expansion node exists with the same name, merge child expansions.
            for child_expansion in expansion_node.expansions:
                existing_expansion_node.add_expansion(child_expansion)
        else:
            # Add the expansion node.
            self._expansions[expansion_node.name] = expansion_node

    def get_expansion(self, expansion_name):  # type: (six.text_type) -> Optional[ExpansionNode]
        """
        Get an expansion node by name.

        :param expansion_name: The name of the expansion

        :return: an :class:`ExpansionNode` instance if the expansion exists, `None` otherwise.
        """

        return self._expansions.get(expansion_name)

    def find_objects(self, obj):  # type: (Any) -> List[Dict[Any, Any]]
        """
        Find all objects in obj that match the type of the type node.

        :param obj: A dictionary or list of dictionaries to search, recursively

        :return: a list of dictionary objects that have a "_type" key value that matches the type of this node.
        """
        objects = []  # type: List[Dict[Any, Any]]

        if isinstance(obj, dict):
            # obj is a dictionary, so it is a potential match...
            object_type = obj.get('_type')
            if object_type == self.type:
                # Found a match!
                objects.append(obj)
            else:
                # Not a match. Check each value of the dictionary for matches.
                for sub_object in six.itervalues(obj):
                    objects.extend(self.find_objects(sub_object))
        elif isinstance(obj, list):
            # obj is a list. Check each element of the list for matches.
            for sub_object in obj:
                objects.extend(self.find_objects(sub_object))

        return objects

    @property
    def expansions(self):  # type: () -> List[ExpansionNode]
        """
        The type node's list of expansions.
        """
        return list(six.itervalues(self._expansions))

    def to_dict(self):  # type: () -> Dict[six.text_type, List[six.text_type]]
        """
        Convert the tree node to its dictionary representation.

        :return: an expansion dictionary that represents the type and expansions of this tree node.
        """
        expansion_strings = []  # type: List[six.text_type]

        for expansion in self.expansions:
            expansion_strings.extend(expansion.to_strings())

        return {
            self.type: expansion_strings,
        }


class ExpansionNode(TypeNode):
    """
    Represents a expansion node for an expansion tree.

    If an expansion node has its own expansions, it can also function as a type node.
    """

    def __init__(
        self,
        node_type,  # type: six.text_type
        name,  # type: six.text_type
        source_field,  # type: six.text_type
        destination_field,  # type: six.text_type
        service,  # type: six.text_type
        action,  # type: six.text_type
        request_field,  # type: six.text_type
        response_field,  # type: six.text_type
        raise_action_errors=True,  # type: bool
    ):
        # type: (...) -> None
        """
        Create a new `ExpansionNode` instance.

        :param node_type: The node type name
        :param name: The node name
        :param source_field: The type's source field name for the expansion identifier
        :param destination_field: The type's destination field name for the expansion result
        :param service: The name of the service that satisfies the expansion
        :param action: The name of the service action that satisfies the expansion
        :param request_field: The name of the field for the expansion request's body
        :param response_field: The name of the field for the expansion response's body
        :param raise_action_errors: Tells the client whether to raise an exception if the expansion action returns an
                                    error response (defaults to True)
        """
        super(ExpansionNode, self).__init__(node_type)
        self.name = name
        self.source_field = source_field
        self.destination_field = destination_field
        self.service = service
        self.action = action
        self.request_field = request_field
        self.response_field = response_field
        self.raise_action_errors = raise_action_errors

    def to_strings(self):  # type: () -> List[six.text_type]
        """
        Convert the expansion node to a list of expansion strings.

        :return: a list of expansion strings that represent the leaf nodes of the expansion tree.
        """
        result = []  # type: List[six.text_type]

        if not self.expansions:
            result.append(self.name)
        else:
            for expansion in self.expansions:
                result.extend('{}.{}'.format(self.name, es) for es in expansion.to_strings())

        return result


TypeRoutes = Dict[
    six.text_type,
    Dict[six.text_type, six.text_type],
]
TypeExpansions = Dict[
    six.text_type,
    Dict[
        six.text_type,
        Dict[
            six.text_type,
            Union[six.text_type, bool],
        ],
    ],
]
Expansions = Dict[six.text_type, List[six.text_type]]


class ExpansionConverter(object):
    """
    A utility class for converting the compact dictionary representation of expansions to expansion trees (and back
    again).
    """

    def __init__(self, type_routes, type_expansions):  # type: (TypeRoutes, TypeExpansions) -> None
        """
        Create an ExpansionConverter instance.

        Type Routes:

        To satisfy an expansion, the expansion processing code needs to know which service action to call and how to
        call it. Type routes solve this problem by by giving the expansion processing code all the information in needs
        to properly call a service action to satisfy an expansion.

        Type Routes Configuration Format::

            {
                "<route>": {
                    "service": "<service name>",
                    "action": "<action name>",
                    "request_field": "<request field name>",
                    "response_field": "<response field name>",
                },
                ...
            }

            <route> is the name of the expansion route, to be referenced from the
                type expansions configuration
            <service name> is the name of the service to call.
            <action name> is the name of the action to call.
            <request field> is the name of the field to use in the ActionRequest
                body. The value of the field will be the expansion identifier
                extracted from the object being expanded.
            <response field> is the name of the field returned in the
                ActionResponse body that contains the expansion object.

        Type Expansions:

        Type expansions detail the expansions that are supported for each type and the routes to use to expand them. If
        a type wishes to support expansions, it must have a corresponding entry in the Type Expansions Configuration
        dictionary.

        Type Expansions Configuration Format::

            {
                "<type>": {
                    "<expansion name>": {
                        "type": "<expansion type>",
                        "route": "<expansion route>",
                        "source_field": "<source field name>",
                        "destination_field": "<destination field name>",
                        "raise_action_errors": <bool>,
                    },
                    ...
                },
                ...
            }

            <type> is a type for which you are defining expansions.
            <expansion name> is the name of an expansion.
            <expansion type> is the type of the expansion. This is used to look up
                the type of the values returned by the expansion in this Type Expansions
                Configuration dictionary for the purpose of processing nested/recursive
                expansions.
            <expansion route> is a reference to the route to use to process the
                expansion. This is used to look up the appropriate expansion route in
                the Type Routes Configuration.
            <source field name> is the name of the source field that contains the
                identifier for obtaining the expansion object.
            <destination field name> is the name of the destination field into which
                the expansion object will be placed.

        :param type_routes: A type route configuration dictionary
        :param type_expansions: A type expansions configuration dictionary
        """
        self.type_routes = type_routes
        self.type_expansions = type_expansions

    def dict_to_trees(self, expansion_dict):  # type: (Expansions) -> List[TypeNode]
        """
        Convert an expansion dictionary to a list of expansion trees.

        Expansion Dictionary Format::

            {
                "<type>": ["<expansion string>", ...],
                ...
            }

            <type> is the type of object to expand.
            <expansion string> is a string with the following format:
                <expansion string> => <expansion name>[.<expansion string>]

        :param expansion_dict: An expansion dictionary (see below)

        :return: a list of expansion trees (:class:`TypeNode` instances).
        """
        trees = []  # type: List[TypeNode]
        for node_type, expansion_list in six.iteritems(expansion_dict):
            type_node = TypeNode(node_type=node_type)

            for expansion_string in expansion_list:
                expansion_node = type_node

                for expansion_name in expansion_string.split('.'):
                    child_expansion_node = expansion_node.get_expansion(expansion_name)

                    if not child_expansion_node:
                        type_expansion = self.type_expansions[expansion_node.type][expansion_name]
                        type_route = self.type_routes[cast(six.text_type, type_expansion['route'])]
                        if type_expansion['destination_field'] == type_expansion['source_field']:
                            raise ValueError(
                                'Expansion configuration destination_field error: '
                                'destination_field can not have the same name as the source_field: '
                                '{}'.format(type_expansion['source_field'])
                            )
                        child_expansion_node = ExpansionNode(
                            node_type=cast(six.text_type, type_expansion['type']),
                            name=expansion_name,
                            source_field=cast(six.text_type, type_expansion['source_field']),
                            destination_field=cast(six.text_type, type_expansion['destination_field']),
                            service=type_route['service'],
                            action=type_route['action'],
                            request_field=type_route['request_field'],
                            response_field=type_route['response_field'],
                            raise_action_errors=cast(bool, type_expansion.get('raise_action_errors', False)),
                        )
                        expansion_node.add_expansion(child_expansion_node)

                    expansion_node = child_expansion_node

            trees.append(type_node)

        return trees

    @staticmethod
    def trees_to_dict(trees_list):  # type: (List[TypeNode]) -> Dict[six.text_type, List[six.text_type]]
        """
        Convert a list of :class:`TypeNode` objects to an expansion dictionary.

        :param trees_list: A list of :class:`TypeNode` instances

        :return: An expansion dictionary that represents the expansions detailed in the provided expansions tree nodes
        """
        result = {}  # type: Dict[six.text_type, List[six.text_type]]

        for tree in trees_list:
            result.update(tree.to_dict())

        return result
