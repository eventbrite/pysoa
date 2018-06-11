from __future__ import absolute_import, unicode_literals

import codecs
import collections
import enum
import importlib
import inspect
import json
import os
import re
import sys

import attr
from conformity import fields
import six

from pysoa.common.settings import Settings


PARAM_DOC_RE = re.compile(r'^:param\s+(?P<arg_name>[a-zA-Z0-9_]+):')
PARAM_TYPE_RE = re.compile(r'^:type\s+(?P<arg_name>[a-zA-Z0-9_]+):')
SINGLE_BACKTICK_RE = re.compile(r'([^`]+|^)`([^`\n]+)`([^_`]+?|$)')

TO_DOCUMENT = (
    'pysoa.client.client:Client',
    'pysoa.client.client:Client.JobError',
    'pysoa.client.client:Client.CallActionError',
    'pysoa.client.client:ServiceHandler',
    'pysoa.client.expander:ExpansionSettings',
    'pysoa.client.middleware:ClientMiddleware',
    'pysoa.client.settings:PolymorphicClientSettings',
    'pysoa.common.metrics:Counter',
    'pysoa.common.metrics:MetricsRecorder',
    'pysoa.common.metrics:NoOpMetricsRecorder',
    'pysoa.common.metrics:Timer',
    'pysoa.common.metrics:TimerResolution',
    'pysoa.common.transport.base:ClientTransport',
    'pysoa.common.transport.base:ServerTransport',
    'pysoa.common.transport.local:LocalClientTransport',
    'pysoa.common.transport.local:LocalServerTransport',
    'pysoa.common.transport.redis_gateway.client:RedisClientTransport',
    'pysoa.common.transport.redis_gateway.server:RedisServerTransport',
    'pysoa.common.types:ActionRequest',
    'pysoa.common.types:ActionResponse',
    'pysoa.common.types:Error',
    'pysoa.common.types:JobRequest',
    'pysoa.common.types:JobResponse',
    'pysoa.server.action.base:Action',
    'pysoa.server.action.introspection:IntrospectionAction',
    'pysoa.server.action.status:BaseStatusAction',
    'pysoa.server.action.status:StatusActionFactory',
    'pysoa.server.action.switched:SwitchedAction',
    'pysoa.server.middleware:ServerMiddleware',
    'pysoa.server.server:Server',
    'pysoa.server.settings:PolymorphicServerSettings',
    'pysoa.server.standalone:simple_main',
    'pysoa.server.standalone:django_main',
    'pysoa.server.types:EnrichedActionRequest',
)

PREAMBLE = """PySOA Reference Documentation
=============================

This file contains the reference documentation for the classes and functions you are likely to consume when using
PySOA. It does not contain the reference documentation for all code in PySOA, which you can view by browsing the
`source code <https://github.com/eventbrite/pysoa/tree/master/pysoa>`_.

**NOTE:** In each place where you see ``union[str, unicode]``, this means that the parameter type should be or the
return type will be a ``str`` (Unicode) in Python 3 and a ``unicode`` in Python 2. You may not use ``str`` in Python
2.

.. contents:: Contents
   :depth: 3
   :backlinks: none"""


NO_DEFAULT = object()


def _clean_literals(documentation):
    # Make all single backticks double, in reStructuredText form, but only if not part of a link (`hello`_) and not
    # already a double or triple backtick.
    return SINGLE_BACKTICK_RE.sub('\g<1>``\g<2>``\g<3>', documentation)


# noinspection PyTypeChecker
def get_function_parsed_docstring(docstring, function_object):
    docstring = inspect.cleandoc(docstring)
    arg_spec = inspect.getargspec(function_object)

    context = None
    returns = []
    return_type = []
    parameters = collections.OrderedDict()
    raises = []

    remaining = []
    for line in docstring.split('\n'):
        if line.startswith(':return:') or line.startswith(':returns:'):
            returns = [line.replace(':return:', '').replace(':returns:', '').strip()]
            context = returns
        elif line.startswith(':rtype:'):
            return_type = [line.replace(':rtype:', '').strip()]
            context = return_type
        elif line.startswith(':raise:') or line.startswith(':raises:'):
            raises.append(line.replace(':raise:', '').replace(':raises:', '').strip())
            context = raises
        elif PARAM_DOC_RE.match(line):
            match = PARAM_DOC_RE.match(line)
            if match.group('arg_name') not in parameters:
                parameters[match.group('arg_name')] = {}
            parameters[match.group('arg_name')]['docs'] = [line.replace(match.group(0), '').strip()]
            context = parameters[match.group('arg_name')]['docs']
        elif PARAM_TYPE_RE.match(line):
            match = PARAM_TYPE_RE.match(line)
            if match.group('arg_name') not in parameters:
                parameters[match.group('arg_name')] = {}
            parameters[match.group('arg_name')]['type'] = [line.replace(match.group(0), '').strip()]
            context = parameters[match.group('arg_name')]['type']
        elif context:
            if line.strip():
                context.append(line.strip())
            else:
                context = None
        else:
            remaining.append(line)

    documentation = ''
    if remaining:
        documentation += '\n\n'
        documentation += _clean_literals('\n'.join(remaining).strip())

    if parameters or arg_spec.args:
        parameter_names = []
        for i, arg in enumerate(arg_spec.args):
            if i > 0 or arg not in ('self', 'cls'):
                parameter_names.append(six.text_type(arg))

        for parameter_name in parameters.keys():
            if parameter_name not in parameter_names:
                parameter_names.append(parameter_name)

        if parameter_names:
            documentation += '\n\nParameters'
            for parameter_name in parameter_names:
                documentation += '\n  - ``{}``'.format(parameter_name)
                if parameter_name in parameters:
                    if parameters[parameter_name].get('type'):
                        documentation += ' (``{}``)'.format(' '.join(parameters[parameter_name]['type']))
                    if parameters[parameter_name].get('docs'):
                        documentation += ' - {}'.format(
                            _clean_literals('\n    '.join(parameters[parameter_name]['docs'])),
                        )

    if returns or return_type:
        documentation += '\n\nReturns'
        if return_type:
            documentation += '\n  ``{}``'.format(' '.join(return_type))
        if returns:
            if return_type:
                documentation += ' - '
            else:
                documentation += '\n  '
            documentation += _clean_literals('\n'.join(returns))

    if raises:
        documentation += '\n\nRaises\n  ``{}``'.format(
            '``, ``'.join(map(six.text_type.strip, ','.join(raises).replace(',,', ',').split(','))),
        )

    if not documentation.strip():
        documentation = '\n\n*(No documentation)*'

    return documentation


def get_function_display_name(name, function_object):
    name = '{}('.format(name)

    has_put_arg = False
    has_put_vararg = False
    arg_spec = inspect.getargspec(function_object)

    if arg_spec.args:
        defaults = ((NO_DEFAULT, ) * (len(arg_spec.args) - len(arg_spec.defaults or []))) + (arg_spec.defaults or ())
        previous_had_default = False
        for i in range(len(arg_spec.args)):
            if i == 0 and arg_spec.args[i] in ('self', 'cls'):
                continue

            if has_put_arg:
                name += ', '
            has_put_arg = True
            if defaults[i] == NO_DEFAULT:
                name += arg_spec.args[i]
            else:
                if not previous_had_default and arg_spec.varargs:
                    name += '*{}, '.format(arg_spec.varargs)
                    has_put_vararg = True
                if isinstance(defaults[i], enum.Enum):
                    default = '{}.{}'.format(defaults[i].__class__.__name__, defaults[i].name)
                elif inspect.isclass(defaults[i]):
                    default = defaults[i].__name__
                else:
                    default = repr(defaults[i]).lstrip('u')
                name += '{}={}'.format(arg_spec.args[i], default)

    if arg_spec.varargs and not has_put_vararg:
        if has_put_arg:
            name += ', '
        has_put_arg = True
        name += '*{}'.format(arg_spec.varargs)

    if arg_spec.keywords:
        if has_put_arg:
            name += ', '
        name += '**{}'.format(arg_spec.keywords)

    name += ')'
    return name


def get_function_documentation(name, module_name, function_object):
    display_name = get_function_display_name(name, function_object)
    documentation = """.. _{module_name}.{simple_function_name}:

``function {function_name}``
++++++++{plus}++

**module:** ``{module_name}``""".format(
        simple_function_name=name,
        function_name=display_name,
        plus='+' * len(display_name),
        module_name=module_name,
    )

    if function_object.__doc__ and function_object.__doc__.strip():
        documentation += get_function_parsed_docstring(function_object.__doc__, function_object)

    return documentation


def get_enum_documentation(class_name, module_name, enum_class_object):
    documentation = """.. _{module_name}.{class_name}:

``enum {class_name}``
+++++++{plus}++

**module:** ``{module_name}``""".format(
        module_name=module_name,
        class_name=class_name,
        plus='+' * len(class_name),
    )

    if enum_class_object.__doc__ and enum_class_object.__doc__.strip():
        documentation += '\n\n{}'.format(_clean_literals(inspect.cleandoc(enum_class_object.__doc__)))

    documentation += '\n\nConstant Values:\n'
    for e in enum_class_object:
        documentation += '\n- ``{}`` (``{}``)'.format(e.name, repr(e.value).lstrip('u'))

    return documentation


def _pretty_introspect(value, depth=1, nullable=''):
    documentation = ''

    first = '  ' * depth
    second = '  ' * (depth + 1)

    description = _clean_literals(getattr(value, 'description', None) or '*(no description)*')

    if isinstance(value, fields.Dictionary):
        documentation += 'strict ``dict``{}: {}\n'.format(nullable, description)
        for k, v in sorted(value.contents.items(), key=lambda i: i[0]):
            documentation += '\n{}- ``{}`` - {}'.format(first, k, _pretty_introspect(v, depth + 1))
        documentation += '\n'
        if value.allow_extra_keys:
            documentation += '\n{}Extra keys of any value are allowed.'.format(first)
        if value.optional_keys:
            if value.allow_extra_keys:
                documentation += ' '
            else:
                documentation += '\n{}'.format(first)
            documentation += 'Optional keys: ``{}``\n'.format('``, ``'.join(value.optional_keys))
    elif isinstance(value, fields.SchemalessDictionary):
        documentation += 'flexible ``dict``{}: {}\n'.format(nullable, description)
        documentation += '\n{}keys\n{}{}\n'.format(first, second, _pretty_introspect(value.key_type, depth + 1))
        documentation += '\n{}values\n{}{}\n'.format(first, second, _pretty_introspect(value.value_type, depth + 1))
    elif isinstance(value, fields.List):
        documentation += '``list``{}: {}\n'.format(nullable, description)
        documentation += '\n{}values\n{}{}'.format(first, second, _pretty_introspect(value.contents, depth + 1))
    elif isinstance(value, fields.Nullable):
        documentation += _pretty_introspect(value.field, depth, nullable=' (nullable)')
    elif isinstance(value, fields.Any):
        documentation += 'any of the types bulleted below{}: {}\n'.format(nullable, description)
        for v in value.options:
            documentation += '\n{}- {}'.format(first, _pretty_introspect(v, depth + 1))
        documentation += '\n'
    elif isinstance(value, fields.Polymorph):
        documentation += 'schema switching on value of ``{}``{}: {}\n'.format(value.switch_field, nullable, description)
        for k, v in sorted(value.contents_map.items(), key=lambda i: i[0]):
            documentation += '\n{spaces}- ``{field} == {value}`` - {doc}'.format(
                spaces=first,
                field=value.switch_field,
                value=repr(k).lstrip('u'),
                doc=_pretty_introspect(v, depth + 1),
            )
        documentation += '\n'
    else:
        introspection = value.introspect()
        documentation += '``{}``{}: {}'.format(introspection.pop('type'), nullable, description)
        introspection.pop('description', None)
        if introspection:
            documentation += ' (additional information: ``{}``)'.format(introspection)

    return documentation


def get_settings_schema_documentation(class_name, module_name, settings_class_object):
    documentation = """.. _{module_name}.{class_name}

``settings schema class {class_name}``
++++++++++++++++++++++++{plus}++

**module:** ``{module_name}``""".format(
        module_name=module_name,
        class_name=class_name,
        plus='+' * len(class_name)
    )

    if settings_class_object.__doc__ and settings_class_object.__doc__.strip():
        documentation += '\n\n{}'.format(_clean_literals(inspect.cleandoc(settings_class_object.__doc__)))

    documentation += """

Settings Schema Definition
**************************
"""

    for k, v in sorted(settings_class_object.schema.items(), key=lambda i: i[0]):
        documentation += '\n- ``{}`` - {}'.format(k, _pretty_introspect(v))

    documentation = documentation.strip()

    if settings_class_object.defaults:
        documentation += """

Default Values
**************

Keys present in the dict below can be omitted from compliant settings dicts, in which case the values below will
apply as the default values.

.. code-block:: python
"""

        for line in json.dumps(
            settings_class_object.defaults,
            ensure_ascii=False,
            indent=4,
            sort_keys=True,
        ).split('\n'):
            documentation += '\n    {}'.format(line.rstrip())

    return documentation


def get_class_documentation(class_name, module_name, class_object):
    is_abstract = inspect.isabstract(class_object)

    documentation = """.. _{module_name}.{class_name}:

``{abstract}class {class_name}``
++++++++{plus}++

**module:** ``{module_name}``""".format(
        abstract='abstract ' if is_abstract else '',
        module_name=module_name,
        class_name=class_name,
        plus='+' * (len(class_name) + (9 if is_abstract else 0)),
    )

    def get_class_tree_docs(tree_node, depth):
        item, _ = tree_node[0]

        tree_docs = ''

        if item == object:
            depth -= 2
        else:
            if not item.__module__ or item.__module__ == '__builtin__':
                item_name = '``{}``'.format(item.__name__)
            elif not item.__module__.startswith('pysoa'):
                item_name = '``{}.{}``'.format(item.__module__, item.__name__)
            else:
                if item == class_object:
                    item_name = '``{}``'.format(item.__name__)
                else:
                    item_name = '`{}.{}`_'.format(item.__module__, item.__name__)
            tree_docs += '\n\n{}- {}'.format(' ' * depth, item_name)

        if len(tree_node) == 2:
            tree_docs += get_class_tree_docs(tree_node[1], depth + 2)

        return tree_docs

    class_tree = inspect.getclasstree([class_object])

    documentation += '\n\n- ``object``'
    documentation += get_class_tree_docs(class_tree, 2)

    if class_object.__doc__ and class_object.__doc__.strip():
        documentation += '\n\n{}'.format(_clean_literals(inspect.cleandoc(class_object.__doc__)))

    members = inspect.getmembers(class_object)

    if getattr(class_object, '__attrs_attrs__', None):
        documentation += '\n\n.. _{module_name}.{class_name}-attrs-docs:\n\nAttrs Properties\n****************\n'.format(
            module_name=module_name,
            class_name=class_name,
        )
        for attribute in class_object.__attrs_attrs__:
            documentation += '\n- ``{name}``{required}'.format(
                name=attribute.name,
                required=' (required)' if attribute.default is attr.NOTHING else '',
            )
    else:
        constructor = next(m for n, m in members if n == '__init__') if '__init__' in class_object.__dict__ else None
        if constructor:
            documentation += '\n\n.. _{module_name}.{class_name}-constructor-docs:\n\nConstructor\n***********'.format(
                module_name=module_name,
                class_name=class_name,
            )
            if constructor.__doc__ and constructor.__doc__.strip():
                documentation += '{}'.format(get_function_parsed_docstring(constructor.__doc__, constructor))
            else:
                documentation += '\n\n*(No documentation)*'

    for member_name, member in sorted(members, key=lambda x: x[0]):
        if member_name in class_object.__dict__ and (
            not member_name.startswith('_') or
            member_name in ('__call__', '__enter__', '__exit__')
        ):
            if inspect.ismethod(member):
                display_name = '``{static}method {method_name}``'.format(
                    static='static ' if getattr(member, '__self__', None) == class_object else '',
                    method_name=get_function_display_name(member_name, member)
                )
                documentation += '\n\n.. _{module_name}.{class_name}.{method_name}:\n\n{display_name}\n'.format(
                    module_name=module_name,
                    class_name=class_name,
                    method_name=member_name,
                    display_name=display_name,
                )
                documentation += ('*' * len(display_name))

                if member.__doc__ and member.__doc__.strip():
                    documentation += get_function_parsed_docstring(member.__doc__, member)
                else:
                    documentation += '\n\n*(No documentation)*'
            elif isinstance(member, property):
                display_name = '``property {}``'.format(member_name)
                documentation += '\n\n.. _{module_name}.{class_name}.{property_name}:\n\n{display_name}\n'.format(
                    module_name=module_name,
                    class_name=class_name,
                    property_name=member_name,
                    display_name=display_name,
                )
                documentation += ('*' * len(display_name))

                primary_doc_source = member.fget or member.fset or member.fdel

                if primary_doc_source and primary_doc_source.__doc__ and primary_doc_source.__doc__.strip():
                    documentation += get_function_parsed_docstring(primary_doc_source.__doc__, primary_doc_source)

                if not member.fset and not member.fdel:
                    documentation += '\n\n*(Property is read-only)*'
                else:
                    if member.fset:
                        documentation += '\n\n**Setter**'
                        documentation += get_function_parsed_docstring(member.fset.__doc__, member.fset)
                    else:
                        documentation += '\n\n*(Property cannot be set)*'

                    if member.fdel:
                        documentation += '\n\n**Deleter**'
                        documentation += get_function_parsed_docstring(member.fdel.__doc__, member.fdel)
                    else:
                        documentation += '\n\n*(Property cannot be deleted)*'

    return documentation


def get_module_documentation(name, module_object):
    return '``module {module_name}``\n+++++++++{plus}++\n\n{documentation}'.format(
        module_name=name,
        plus='+' * len(name),
        documentation=_clean_literals(inspect.cleandoc(module_object.__doc__)),
    )


def document():
    with codecs.open(
        '{}/reference.rst'.format(os.path.dirname(os.path.realpath(__file__))),
        'wb',
        encoding='utf-8'
    ) as documentation:
        documentation.write(PREAMBLE)

        for item in TO_DOCUMENT:
            if ':' in item:
                item_module_name, item_name = item.split(':', 1)
            else:
                item_module_name, item_name = item, None

            prev_path_0 = sys.path[0]
            sys.path[0] = ''
            try:
                item_module = importlib.import_module(item_module_name)
            finally:
                sys.path[0] = prev_path_0

            if not item_name:
                documentation.write('\n\n\n')
                documentation.write(get_module_documentation(item_module_name, item_module))
            else:
                name_hierarchy = item_name.split('.')
                item_object = getattr(item_module, name_hierarchy[0])
                for name in name_hierarchy[1:]:
                    item_object = getattr(item_object, name)

                if inspect.isclass(item_object):
                    documentation.write('\n\n\n')
                    if issubclass(item_object, enum.Enum):
                        documentation.write(get_enum_documentation(item_name, item_module_name, item_object))
                    elif issubclass(item_object, Settings):
                        documentation.write(get_settings_schema_documentation(item_name, item_module_name, item_object))
                    else:
                        documentation.write(get_class_documentation(item_name, item_module_name, item_object))
                elif inspect.isfunction(item_object):
                    documentation.write('\n\n\n')
                    documentation.write(get_function_documentation(item_name, item_module_name, item_object))
                else:
                    sys.stderr.write(
                        'WARNING: Unable to document {i}: Type {t} is not a module, class, or function'.format(
                            i=item,
                            t=type(item_object),
                        )
                    )

        documentation.write('\n')


if __name__ == '__main__':
    document()
