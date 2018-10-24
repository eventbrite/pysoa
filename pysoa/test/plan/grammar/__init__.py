from __future__ import (
    absolute_import,
    unicode_literals,
)

import inspect
import re

import six

from pysoa.test.plan.grammar.data_types import (
    data_type_descriptions,
    get_all_data_type_names,
)
from pysoa.test.plan.grammar.directive import get_all_directives
import pysoa.test.plan.grammar.directives  # noqa F401


##################################################
# IMPORTANT NOTE
#
# If you alter or add to any of the documentation below, or if you add more grammar directives, you must run
# `docs/update_test_plan_docs.sh` from the root of this project first, to ensure that the latest generated
# documentation makes its way into the `testing.rst` documentation file.
##################################################

__SINGLE_BACKTICK_RE = re.compile(r'([^`]+|^)`([^`\n]+)`([^_`]+?|$)')


def __wrap_documentation_line(documentation_line, first_indent=4, second_indent=4):
    to_return = ''
    first_indent_str = (' ' * first_indent)
    second_indent_str = first_indent_str + (' ' * second_indent)
    remaining = first_indent_str + documentation_line.strip()

    while len(remaining) > 120:
        index = remaining.rindex(' ', 0, 120)
        to_return += remaining[0:index] + '\n'
        remaining = second_indent_str + remaining[index:].strip()

    to_return += remaining
    return to_return


__doc__ = """Writing a Test Fixture
**********************

Within a test fixture, an individual test case is a block of text with the first ``test name:`` line being the name of
the test, followed by multiple directives to instruct the behavior of the test. A blank line ends the test case::

    test name: this_is_the_test_name_must_be_valid_method_name
    test description: This describes what the test does
    action1_name: input: foo_request_var_name: bar_value
    action1_name: expect: no errors
    action1_name: expect: attribute value: baz_response_var_name: qux_value
    # This is a comment
    action2_name: input: foo: bar

    test name: this_is_the_next_test
    etc...


You may also set global directives that will apply to all of the following tests in the same file with the ``global``
modifier (but will not apply to tests defined before the global directives)::

    get_user: global input int: user_id: [[test_users.1.id]]
    get_user: global job context input int: switches.0: 5

    test name: get_user_url_works
    test description: Test that get_user_url works
    get_user: expect: no errors
    get_user_url: input: username: [[GET_USER.0.user.username]]
    get_user_url: job context input: locale: en_US
    get_user_url: expect: no errors
    get_user_url: expect: attribute value: user_url: https://example.net/en/u/[[GET_USER.0.user.username]]/


This later case makes use of variable substitutions. The first one, ``[[test_users.1.id]]``, gets replaced with the
``id`` value from the second dict (index 1) in the ``test_users`` list in the ``model_constants`` class attribute
defined earlier. The first two lines of this example define global directives that, by themselves, do nothing. In the
test case, the ``get_user: expect: no errors`` directive executes the ``get_user`` action defined from the global
directives. This makes all the response values from that ``get_user`` action available for variable substitutions for
all future action cases in this test case (but not for future test cases). The ``get_user_url`` action case makes use
of this with the ``[[GET_USER.0.user.username]]`` variable substitution, which references the username from the user
dict returned by the response to the first (index 0) call to ``get_user``.

You'll notice that this variable substitution has an index of 0, even though our ``get_user`` action call did not. By
default, the first call to an action in a test case has an index of 0. However, subsequent calls to the same action
in the same test case will require an explicit index. For clarity, it is often best to include indexes with all action
calls when your test case calls an action multiple times::

    test name: get_user_multiple_times
    test description: Demonstrate action indexes
    get_user.0: input: id: 1838
    get_user.0: expect: no errors
    get_user.1: input: id: 1792
    get_user.1: expect: no errors

Input data and attribute value expectations are defined using path structures that get translated into dictionaries and
lists based on a string path in the following format:

- Dots indicate nested data structures
- Numeric path names indicate array indices
- Individual path elements that contain dots or which want to be stringified numbers can be escaped by enclosing in {}.

Examples::

    foo.bar.baz         => {'foo': {'bar': {'baz': $value }}}
    foo.bar.0           => {'foo': {'bar': [ $value ]}}}
    foo.bar.0.baz       => {'foo': {'bar': [{'baz': $value }]}}}
    foo.{bar.baz}       => {'foo': {'bar.baz': $value }}
    foo.{0}             => {'foo': {'0': $value }}

There are many directives available to you for creating rich and complex test fixtures and test cases. The rest of
this section's documentation details those directives.


Test Fixture Full Grammar
-------------------------

This is the full grammar for test fixture files, presented in the same style as the `Python Grammar Specification
<https://docs.python.org/3/reference/grammar.html>`_. Detailed usage for each directive and the supported data types
follows. ::

"""

__doc__ += """    NEWLINE: [\\n]
    ALPHA: [a-zA-Z]+
    NUM: [0-9]+
    ALPHANUM: [a-zA-Z0-9]+
    NAME: ALPHA (ALPHANUM | '_')*
    HYPHENATED_NAME: NAME (NAME | '-')*
    PLAIN_LANGUAGE: ~NEWLINE

"""

__base_types = {
    'action': 'NAME',
    'action_index': 'NUM',
    'comment': 'PLAIN_LANGUAGE',
    'data_type': "'{}'".format("' | '".join(get_all_data_type_names())),
    'description': 'PLAIN_LANGUAGE',
    'error_code': 'NAME',
    'error_message': 'PLAIN_LANGUAGE',
    'field_name': "HYPHENATED_NAME (HYPHENATED_NAME | '.')*",
    'job_slot': "'context' | 'control'",
    'name': 'NAME',
    'reason': 'PLAIN_LANGUAGE',
    'value': 'PLAIN_LANGUAGE',
    'variable_name': 'ALPHANUM (ALPHANUM | [-_.{}])*',
}

for __directive_class in get_all_directives():
    for k, v in six.iteritems(__directive_class.supplies_additional_grammar_types()):
        if k not in __base_types:
            __base_types[k] = v

for k in sorted(__base_types.keys()):
    __doc__ += __wrap_documentation_line('{}: {}'.format(k, __base_types[k])) + '\n'
__doc__ += '\n'

for __directive_class in get_all_directives():
    __doc__ += __wrap_documentation_line(__directive_class.name() + ': ' + repr(__directive_class()).strip()) + '\n'

__doc__ += '\n' + __wrap_documentation_line('global_directive: {}'.format(
    ' | '.join(c.name() for c in get_all_directives() if "['global']" in repr(c()) or c.name() == 'fixture_comment')
)) + '\n'

__doc__ += '\n' + __wrap_documentation_line('test_directive: {}'.format(
    ' | '.join(c.name() for c in get_all_directives() if c.name() not in ('test_name', 'test_description'))
)) + '\n'

__doc__ += """
    global_case: global_directive NEWLINE (global_directive NEWLINE)*
    test_case: test_name NEWLINE test_description NEWLINE test_directive NEWLINE (test_directive NEWLINE)*

    fixture: (global_case | test_case) NEWLINE ((global_case | test_case) NEWLINE)*


Some notes about this grammar:

- A blank line ends the test case.
- ``action_index`` defaults to ``0`` if not specified.
- ``data_type`` defaults to ``str`` (a unicode string) if not specified.


Data Type Descriptions
----------------------

This is an explanation for all available data types:

"""

for name in get_all_data_type_names():
    __doc__ += __wrap_documentation_line('- ``{}``: {}'.format(name, data_type_descriptions[name]), 0, 2) + '\n'

__doc__ += """

Dates and Times:
~~~~~~~~~~~~~~~~

Some important notes about dates and times:

- When the data type is ``time``, you can use ``[hour],[minute],[second],[millisecond]`` to pass integer arguments
  directly to the ``time`` type constructor, or you can use one of the following:

  + ``now``: current ``time`` (in local time one)
  + ``utc_now``: current ``time`` (in UTC time)
  + ``midnight``: a midnight time (all zeroes)

- When the data type is ``date``, you can use ``today`` to use current date, or ``[year],[month],[day]`` to pass
  integer arguments directly to the ``date`` type constructor.
- When the data type is ``datetime``, you can use ``[year],[month],[day],[hour],[minute],[second],[millisecond]`` to
  pass integer arguments directly to the ``datetime`` constructor, or you can use one of the following:

  + ``now``: current ``datetime`` (in local timezone)
  + ``utc_now``: current ``datetime`` (in UTC timezone)
  + ``midnight``: start of the date ``datetime`` (in local timezone)
  + ``utc_midnight``: start of the date ``datetime`` (in UTC timezone)

- If you need to specify a time delta, you can do so using the same ``timedelta`` arguments in the order ``days``,
  ``hours``, ``minutes``, ``seconds`` and ``microseconds``), like:

  + ``now +1``: current ``datetime`` plus 1 day (in local timezone)
  + ``utc_now +0,6``: current ``datetime`` or ``time`` plus 6 hours (in UTC timezone)
  + ``midnight +0,3,30``: start of the date ``datetime`` or midnight ``time`` plus 3 hours 30 minutes (in local
    timezone)
  + ``utc_midnight +4,12``: start of the date ``datetime`` plus 4 days 12 hours (in UTC timezone)


Detailed Syntax Description
---------------------------

You should familiarize yourself with the details of all available directives:


"""


for __directive_class in get_all_directives():
    __name = __directive_class.name().replace('_', ' ').title() + ' Directive'
    __doc__ += (
        '' + __name + '\n' +
        ('~' * len(__name)) + '\n\n' +
        __SINGLE_BACKTICK_RE.sub(r'\g<1>``\g<2>``\g<3>', inspect.cleandoc(__directive_class.__doc__ or '')) + '\n\n' +
        '(from: ``' + __directive_class.__module__ + '``)' + '\n\n' +
        'Syntax::\n\n' + __wrap_documentation_line(repr(__directive_class())) + '\n\n\n'
    )
