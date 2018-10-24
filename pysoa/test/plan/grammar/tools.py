from __future__ import (
    absolute_import,
    unicode_literals,
)

import re

from pyparsing import (
    And,
    Literal,
    MatchFirst,
    Optional,
    Or,
    Regex,
    White,
    Word,
)
import six

from pysoa.test.plan.errors import StatusError


ENSURE_ACTION_SUBSTITUTION_DEFAULT_INDEX_RE = re.compile(r'\[\[([A-Z_-]+)\.(?!\d)([a-zA-Z0-9_.{}-]+)*\]\]')
VARIABLE_SUBSTITUTION_RE = re.compile(r'(\[\[(([a-zA-Z_-]+\.\d+)?([a-zA-Z0-9_.{}-]+)*)\]\])')
SOURCE_PATH_FIND_PATH_WITHOUT_INDEX_TO_ADD_INDEX_ZERO = re.compile(r'^([\w_]+)\.(?!\d+\.)')


def path_put(out, path, value):
    """
    Put data into dict structures based on a string path in the following format:

        - Dots indicate nested data structures
        - Numeric path names indicate array indices
        - Individual path elements that contain dots or which want to be stringified numbers can be escaped by
          enclosing in {}.

    Examples:
        foo.bar.baz         => {'foo': {'bar': {'baz': 'value'}}}
        foo.bar.0           => {'foo': {'bar': [ 'value' ] }}}
        foo.bar.0.baz       => {'foo': {'bar': [ { 'baz': 'value' } ] }}}
        foo.{bar.baz}       => {'foo': {'bar.baz': 'value'}}
        foo.{0}             => {'foo': {'0': 'value'}}
    """
    slot, path_rest = _path_get_next_path_element(path)

    if path_rest is None:
        # Set tip of the branch value (no more recursion at this point)
        if type(out) == list:
            _vivify_array(out, slot, dict)
        out[slot] = value
    else:
        next_slot, x = _path_get_next_path_element(path_rest)
        if next_slot is not None and type(next_slot) == int:
            prototype = []
        else:
            prototype = {}

        if type(out) == dict and slot not in out:
            out[slot] = prototype

        if type(out) == list:
            _vivify_array(out, slot, type(prototype))

        path_put(out[slot], path_rest, value)


def _vivify_array(array, count, prototype):
    for i in range(len(array), count + 1):
        array.append(prototype())


def path_get(data, path):
    """
    Converse of path_put. Raises `KeyError` or `IndexError` for unaddressable paths.
    """
    slot, path_rest = _path_get_next_path_element(path)
    if isinstance(data, dict) and slot not in data:
        raise KeyError(slot)

    elif isinstance(data, (list, tuple, set)):
        if type(slot) != int or len(data) < slot + 1:
            raise IndexError(slot)

    if isinstance(data, set):
        data = sorted(list(data))

    if not path_rest:
        return data[slot]

    return path_get(data[slot], path_rest)


def get_all_paths(data, current_path=''):
    paths = []
    if isinstance(data, dict):
        for k, v in six.iteritems(data):
            if isinstance(k, six.string_types) and (k.isdigit() or '.' in k):
                k = '{{{}}}'.format(k)
            paths.extend(get_all_paths(v, _dot_join(current_path, k)))
    elif isinstance(data, (list, set)):
        if isinstance(data, set):
            data = sorted(list(data))
        for i, v in enumerate(data):
            paths.extend(get_all_paths(v, _dot_join(current_path, i)))
    else:
        return [current_path]
    return paths


def _dot_join(a, b):
    if not a:
        return b
    return '.'.join([six.text_type(a), six.text_type(b)])


def _path_get_next_path_element(path):
    # returns next path element and path remainder
    #
    # This is what happens when you don't really think ahead on your language.
    #
    # Supported formats:
    #   1) 'dot' delimited
    #   2) Integer string values will be cast to int unless "escaped."
    #   3) Values between dots can be "escaped" by enclosing in curly braces.  Anything inside the braces will be
    #      taken "as is", but extra curlies inside the escaped value must balance.
    #
    # foo                       => foo
    # foo.bar                   => foo, bar
    # foo.bar.0                 => foo, bar, int(0)
    # foo.bar.0.baz             => foo, bar, int(0), baz
    # foo.{bar.0.baz}           => foo, bar.0.baz
    # foo.{0}.bar               => foo, six.text_type(0), bar
    # foo.{{bar.baz}}.qux       => foo, {bar.baz}, qux
    #
    if not path:
        return None, None

    next_element_chars = []
    brace = 0
    was_in_brace = False
    i = 0

    for i, char in enumerate(path):
        if char == '{':
            was_in_brace = True
            brace += 1
            if brace == 1:
                continue

        if char == '}':
            brace -= 1
            if brace == 0:
                continue

        if char == '.' and not brace:
            break

        next_element_chars.append(char)

    next_element = ''.join(next_element_chars)
    if not was_in_brace and next_element.isdigit():
        next_element = int(next_element)

    remainder = path[i + 1:] or None

    return next_element, remainder


def recursive_parse_expr_repr(parse_expression):
    """
    Return a reasonable BNF(ish) style representation of a parse_expression.
    """
    if isinstance(parse_expression, And):
        return ' '.join([recursive_parse_expr_repr(x) for x in parse_expression.exprs])

    if isinstance(parse_expression, Optional):
        if isinstance(parse_expression.expr, White):
            return ''
        else:
            return ''.join(('[', recursive_parse_expr_repr(parse_expression.expr), ']'))

    if isinstance(parse_expression, (MatchFirst, Or)):
        return '(({}))'.format(') | ('.join([recursive_parse_expr_repr(x) for x in parse_expression.exprs]))

    if isinstance(parse_expression, White):
        return ''

    if isinstance(parse_expression, Literal):
        return "'{}'".format(parse_expression.match)

    if isinstance(parse_expression, Word):
        return parse_expression.resultsName or parse_expression.name

    if isinstance(parse_expression, Regex):
        if parse_expression.resultsName:
            return parse_expression.resultsName
        else:
            return repr(parse_expression)

    return ''


def substitute_variables(data, *sources):
    """
    Overlay [[NAME]] values with values from sources, if possible.
    """
    for path in get_all_paths(data):
        try:
            value = path_get(data, path)
        except (KeyError, IndexError):
            continue
        if not value:
            continue
        if not isinstance(value, six.text_type):
            continue

        replacements = [
            {'token': m[0], 'full_path': m[1], 'action': m[2], 'action_path': m[3] if m[2] else None}
            for m in VARIABLE_SUBSTITUTION_RE.findall(value)
        ]
        if not replacements:
            continue

        for replacement in replacements:
            find_path = replacement['full_path']
            if replacement['action']:
                potential_action_name = replacement['action'].lower()
                for source in sources:
                    if potential_action_name in source:
                        # `action.#` paths don't denote a sublist, unlike most path expressions ... instead, the
                        # entire `action.#` value is a key in a dict, so we need to escape it. The result is
                        # `{action.#}.rest.of.path`.
                        find_path = '{{{}}}{}'.format(potential_action_name, replacement['action_path'])

            try:
                replace_with = _find_path_in_sources(find_path, *sources)
            except KeyError:
                raise StatusError('Could not find value {path} for {replacement} in sources {sources}'.format(
                    path=find_path,
                    replacement=replacement['token'],
                    sources=sources,
                ))

            if value == replacement['token']:
                # preserve the type if this is the only replacement in the value
                value = replace_with
            else:
                value = value.replace(replacement['token'], six.text_type(replace_with))

        path_put(data, path, value)


def _find_path_in_sources(source_path, *sources):
    for source in sources:
        try:
            return path_get(source, source_path)
        except (KeyError, IndexError):
            try:
                return path_get(source, source_path.lower())
            except (KeyError, IndexError):
                try:
                    return path_get(
                        source,
                        SOURCE_PATH_FIND_PATH_WITHOUT_INDEX_TO_ADD_INDEX_ZERO.sub(r'{\1.0}.', source_path.lower())
                    )
                except (KeyError, IndexError):
                    pass

    raise KeyError(source_path)
