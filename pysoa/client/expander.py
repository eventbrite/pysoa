import six


class TypeNode(object):
    """
    Represents a type node for an expansion tree.
    """
    def __init__(self, type):
        """
        Create a new TypeNode instance.

        Args:
            type (str): a type.

        Returns:
            A TypeNode instance.
        """
        self.type = type
        self._expansions = {}

    def add_expansion(self, expansion_node):
        """
        Add a child expansion node to the type node's expansions.

        If an expansion node with the same name is already present in type
        node's expansions, the new and existing expansion node's children
        are merged.

        Args:
            expansion_node: an ExpansionNode instance.

        Returns:
            None
        """
        # Check for existing expansion node with the same name
        existing_expansion_node = self.get_expansion(expansion_node.name)
        if existing_expansion_node:
            # Expansion node exists with the same name, merge child expansions.
            for child_expansion in expansion_node.expansions:
                existing_expansion_node.add_expansion(child_expansion)
        else:
            # Add the expansion node.
            self._expansions[expansion_node.name] = expansion_node

    def get_expansion(self, expansion_name):
        """
        Get an expansion node by name.

        Args:
            expansion_name (str): name of the expansion.

        Returns:
            An ExpansionNode instance if the expansion exists, None otherwise.
        """

        return self._expansions.get(expansion_name)

    def find_objects(self, obj):
        """
        Find all objects in obj that match the type of the type node.

        Args:
            obj: a dictionary or list instance to search.

        Returns:
            A list of dictionary objects that have a "_type" key value that
            matches the type of the type node.
        """
        objects = []
        if isinstance(obj, dict):
            # obj is a dictionary, so it is a potential match...
            obj_type = obj.get('_type')
            if obj_type == self.type:
                # Found a match!
                objects.append(obj)
            elif obj_type is None:
                # Not a match. Check each value of the dictionary for matches.
                for sub_obj in six.itervalues(obj):
                    objects.extend(self.find_objects(sub_obj))
        elif isinstance(obj, list):
            # obj is a list. Check each element of the list for matches.
            for sub_obj in obj:
                objects.extend(self.find_objects(sub_obj))
        return objects

    @property
    def expansions(self):
        """
        The type node's list of expansions.
        """
        return list(six.itervalues(self._expansions))

    def to_dict(self):
        """
        Convert the tree node to its dictionary representation.

        Returns:
            An expansion dictionary that represents the type and expansions of
            the tree node.
        """
        expansion_strings = []
        for expansion in self.expansions:
            expansion_strings.extend(expansion.to_strings())
        return {
            self.type: expansion_strings,
        }


class ExpansionNode(TypeNode):
    """
    Represents a expansion node for an expansion tree.

    If an expansion node has its own expansions, it can also function as a type
    node.
    """
    def __init__(
        self,
        type,
        name,
        source_field,
        dest_field,
        service,
        action,
        request_field,
        response_field,
        raise_action_errors=True,
    ):
        """
        Create a new ExpansionNode instance.

        Args:
            type (str): a type.
            name (str): name of the expansion.
            source_field (str): a type's source field name for the expansion
                identifier.
            dest_field (str): a type's destination field name for the expansion
                result.
            service (str): name of the service that satisfies the expansion.
            action (str): name of the action that satisfies the expansion.
            request_field (str): field name for the expansion's ActionRequest body.
            response_field (str): field name for the expansion's ActionResponse body.
            raise_action_errors (bool): tells the Client not to raise an exception if the
                expansion action returns an error response.

        Returns:
            An ExpansionNode instance.
        """
        super(ExpansionNode, self).__init__(type)
        self.name = name
        self.source_field = source_field
        self.dest_field = dest_field
        self.service = service
        self.action = action
        self.request_field = request_field
        self.response_field = response_field
        self.raise_action_errors = raise_action_errors

    def to_strings(self):
        """
        Convert the expansion node to a list of expansion strings.

        Returns:
            A list of expansion strings that represent the leaf
            nodes of the expansion tree.
        """
        result = []
        if not self.expansions:
            result.append(self.name)
        else:
            for expansion in self.expansions:
                result.extend(
                    "{}.{}".format(self.name, es)
                    for es in expansion.to_strings()
                )
        return result


class ExpansionConverter(object):
    """
    A utility class for converting the compact dictionary representation of
    expansions to expansion trees (and back again).
    """
    def __init__(self, type_routes, type_expansions):
        """
        Create an ExpansionConverter instance.

        Args:
            type_routes (dict): a type route configuration dictionary
                (see below).
            type_expansions (dict): a type expansions configuration dictionary
                (see below).

        Returns:
            An ExpansionConverter instance.

        Type Routes:
        To satisfy an expansion, the expansion processing code needs to know
        which service action to call and how to call it. Type routes solve this
        problem by by giving the expansion processing code all the information
        it needs to properly call a service action to satisfy an expansion.

        <type> is the type of the expansion.
        <service name> is the name of the service to call.
        <action name> is the name of the action to call.
        <request field> is the name of the field to use in the ActionRequest
            body. The value of the field will be the expansion identifier
            extracted from the object being expanded.
        <response field> is the name of the field returned in the
            ActionResponse body that contains the expansion object.

        Type Route Configuration Format:
        {
            "<type>": {
                "service": "<service name>",
                "action": "<action name>",
                "request_field": "<request field name>",
                "response_field": "<response field name>",
            },
            ...
        }

        Type Expansions:
        Type expansions detail the expansions that are supported for each type.
        If a type wishes to support expansions, it must have a corresponding
        entry in the Type Expansions Configuration dictionary.

        <type> is a type for which you are defining expansions.
        <expansion name> is the name of an expansion.
        <expansion type> is the type of the expansion. This is used to look up
            the appropriate expansion route in the Type Route Configuration.
        <source field name> is the name of the field on an object of type
            <type> that contains the value of the expansion identifier.
        <destination field name> is the name of the field on an object of type
            <type> that will be filled with the expanded value.

        Type Expansions Configuration Format:
        {
            "<type>": {
                "<expansion name>": {
                    "type": "<expansion type>",
                    "source_field": "<source field name>",
                    "dest_field": "<destination field name>",
                    "raise_action_errors": <bool>
                },
                ...
            },
            ...
        }
        """
        self.type_routes = type_routes
        self.type_expansions = type_expansions

    def dict_to_trees(self, exp_dict):
        """
        Convert an expansion dictionary to a list of expansion trees.

        Args:
            exp_dict (dict): an expansion dictionary (see below).

        Returns:
            A list of expansion trees (i.e. TreeNode instances).

        Expansion Dictionary Format:
        {
            "<type>": ["<expansion string>", ...],
            ...
        }

        <type> is the type of object to expand.
        <expansion string> is a string with the following format:
            <expansion string> => <expansion name>.<expansion string> |
                <expansion name>

        """
        trees = []
        for exp_type, exp_list in six.iteritems(exp_dict):
            type_node = TypeNode(type=exp_type)
            for exp_string in exp_list:
                expansion_node = type_node
                for exp_name in exp_string.split('.'):
                    child_expansion_node = expansion_node.get_expansion(exp_name)
                    if not child_expansion_node:
                        type_expansion = self.type_expansions[expansion_node.type][exp_name]
                        type_route = self.type_routes[type_expansion['type']]
                        child_expansion_node = ExpansionNode(
                            type=type_expansion['type'],
                            name=exp_name,
                            source_field=type_expansion['source_field'],
                            dest_field=type_expansion['dest_field'],
                            service=type_route['service'],
                            action=type_route['action'],
                            request_field=type_route['request_field'],
                            response_field=type_route['response_field'],
                            raise_action_errors=type_expansion.get('raise_action_errors', False),
                        )
                        expansion_node.add_expansion(child_expansion_node)
                    expansion_node = child_expansion_node
            trees.append(type_node)
        return trees

    def trees_to_dict(self, exp_trees):
        """
        Convert a list of TreeNodes to an expansion dictionary.

        Args:
            exp_trees (list): a list of TreeNode instances.

        Returns:
            An expansion dictionary that represents the expansions detailed in
            the provided expansions tree nodes.
        """
        result = {}
        for exp_tree in exp_trees:
            result.update(exp_tree.to_dict())
        return result
