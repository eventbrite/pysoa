"""
Directives for mocking
"""
from __future__ import (
    absolute_import,
    unicode_literals,
)

import json
import sys
import traceback

from pyparsing import (
    Literal,
    Optional,
    Regex,
    oneOf,
)
import six

from pysoa.common.settings import resolve_python_path
from pysoa.test.compatibility import mock as unittest_mock
from pysoa.test.plan.errors import FixtureSyntaxError
from pysoa.test.plan.grammar.directive import (
    ActionDirective,
    Directive,
    VarValueGrammar,
    register_directive,
)


# __test_plan_prune_traceback = True  # ensure code in this file is not included in failure stack traces

_mock_target_syntax = Regex(r'([a-z_]+[a-z0-9_]*)+(\.[a-z_]+[a-z0-9_]*)*')('mock_target')
_mock_path_syntax = _mock_target_syntax.copy()('mock_path')
_json_syntax = VarValueGrammar.copy()('json')


class _AttrDict(dict):
    def __init__(self, *args, **kwargs):
        super(_AttrDict, self).__init__(*args, **kwargs)
        self.__dict__ = self


class _DeleteAttribute(object):
    def __deepcopy__(self, *_, **__):
        return self


_DELETE_ATTRIBUTE = _DeleteAttribute()


def _mock_any_decoder(o):
    if len(o) == 1 and o.get('mock.ANY', False) is True:
        return unittest_mock.ANY
    return _AttrDict(o)


def _get_python_value_from_json(json_value, file_name, line_number):
    try:
        return json.loads('{{"value": {}}}'.format(json_value), object_hook=_mock_any_decoder)['value']
    except Exception as e:
        raise FixtureSyntaxError(e.args[0], file_name, line_number)


def _ensure_mock_in_target_and_return(test_target, mock_target):
    mock = test_target.setdefault('mock_patches', {}).setdefault(mock_target, {})

    if 'configure' not in mock:
        mock['configure'] = {}
    if 'expectations' not in mock:
        mock['expectations'] = {}

    return mock


def _assemble_mock_path_result(mock, parse_results, file_name, line_number):
    is_exception = is_delete = None
    if getattr(parse_results, 'instruction', None):
        is_exception = parse_results.instruction == 'exception'
        is_delete = parse_results.instruction == 'delete'

    mock_path = parse_results.mock_path

    if is_delete:
        if mock_path.endswith('return_value') or mock_path.endswith('side_effect'):
            raise FixtureSyntaxError(
                'Cannot delete paths ending in special Mock attributes `return_value` or `side_effect`',
                file_name,
                line_number,
            )
        mock['configure'][mock_path] = _DELETE_ATTRIBUTE
    else:
        value = parse_results.value
        if is_exception:
            try:
                if ':' not in value:
                    value = '__builtin__:{}'.format(value) if six.PY2 else 'builtins:{}'.format(value)
                value = resolve_python_path(value)
            except (ImportError, AttributeError) as e:
                raise FixtureSyntaxError(
                    'Could not resolve python path for value "{}" due to error: {}'.format(value, six.text_type(e)),
                    file_name,
                    line_number,
                )
        else:
            value = _get_python_value_from_json(value, file_name, line_number)

        if mock_path.endswith('side_effect'):
            mock['configure'].setdefault(mock_path, []).append(value)
        else:
            mock['configure'][mock_path] = value


def _start_patches(test_target):
    if 'mock_patches' in test_target:
        for mock_target, config in six.iteritems(test_target['mock_patches']):
            config['patcher'] = unittest_mock.patch(mock_target, new=unittest_mock.MagicMock())
            config['magic_mock'] = config['patcher'].start()

            if config['configure']:
                # The code in this came, and is slightly modified, from unittest.mock.Mock
                # "We sort on the number of dots so that attributes are set before we set attributes on attributes"
                for path, value in sorted(config['configure'].items(), key=lambda e: e[0].count('.')):
                    paths = path.split('.')
                    final = paths.pop()
                    obj = config['magic_mock']
                    for entry in paths:
                        obj = getattr(obj, entry)
                    if value is _DELETE_ATTRIBUTE:
                        delattr(obj, final)
                    else:
                        setattr(obj, final, value)


def _assemble_mock_expectations(mock, parse_results, file_name, line_number):
    mock_path = getattr(parse_results, 'mock_path', None) or None
    expectations = mock['expectations'].setdefault(mock_path, {'not_called': False, 'calls': []})

    if getattr(parse_results, 'not', None):
        if expectations['calls']:
            raise FixtureSyntaxError(
                'Cannot combine not-called expectations with other expectations for path "{}"'.format(mock_path),
                file_name,
                line_number,
            )
        expectations['not_called'] = True
    else:
        if expectations['not_called']:
            raise FixtureSyntaxError(
                'Cannot combine not-called expectations with other expectations for path "{}"'.format(mock_path),
                file_name,
                line_number,
            )
        value = _get_python_value_from_json(parse_results.json, file_name, line_number)
        try:
            if len(value) != 2 or not isinstance(value[0], list) or not isinstance(value[1], dict):
                raise Exception
        except Exception:
            raise FixtureSyntaxError(
                'Expected call JSON syntax must be in the form: [[arg1, ...], {"kwarg1": val1, ...}]',
                file_name,
                line_number,
            )
        expectations['calls'].append(value)


def _assert_mock_expectations(test_target):
    if 'mock_patches' in test_target:
        for mock_target, config in six.iteritems(test_target['mock_patches']):
            if 'magic_mock' in config:
                for path, expectations in six.iteritems(config['expectations']):
                    obj = config['magic_mock']
                    if path:
                        for entry in path.split('.'):
                            obj = getattr(obj, entry)

                    actual_calls = obj.call_count
                    if expectations['not_called']:
                        assert actual_calls == 0, (
                            'Expected mock to not have been called. Called {} times.'.format(actual_calls),
                        )
                    elif expectations['calls']:
                        obj.assert_has_calls(
                            [unittest_mock.call(*value[0], **value[1]) for value in expectations['calls']]
                        )
                        expected_calls = len(expectations['calls'])
                        assert actual_calls == expected_calls, (
                            'Expected mock to be called {expected} times. Called {actual} times.'.format(
                                expected=expected_calls,
                                actual=actual_calls
                            ),
                        )


class MockPathResultForTestPlanDirective(Directive):
    """
    Use this to patch a target with `unittest.Mock` and set up a return value or side effect for that mock or any of
    its attributes at any path level. For example, if your module named `example_service.actions.users` imported
    `random`, `uuid`, and `third_party_object`, you could mock those three imported items using the following potential
    directives::

        mock: example_service.actions.users.random: randint.return_value: 31
        mock: example_service.actions.users.uuid: uuid4.side_effect: "abc123"
        mock: example_service.actions.users.uuid: uuid4.side_effect: "def456"
        mock: example_service.actions.users.uuid: uuid4.side_effect: "ghi789"
        mock: example_service.actions.users.third_party_object: return_value: {"id": 3, "name": "Hello, world"}
        mock: example_service.actions.users.third_party_object: foo_attribute.return_value.bar_attribute.side_effect: exception IOError
        mock: example_service.actions.users.third_party_object: foo_attribute.return_value.qux_attribute: delete

    Taking a look at each line in this example:

    * Line 1 sets up `random.randint` to return the value 31. It will return the value 31 every time it is called, no
      matter how many times this is. This is analogous to:

      .. code-block:: python

          mock_random.randint.return_value = 31

    * Lines 2 through 4 set up `uuid.uuid4` to return the strings "abc123", "def456", and "ghi789," in that order.
      Using `side_effect` in this manner, `uuid.uuid4` cannot be called more than three times during the test, per
      standard `Mock` behavior. You must use `side_effect` in this order if you wish to specify multiple different
      return values. This is analogous to:

      .. code-block:: python

          mock_uuid.uuid4.side_effect = ("abc123", "def456", "ghi789")

    * Line 5 sets up `third_party_object` to, when called, return the object `{"id": 3, "name": "Hello, world"}`. Note
      that, when setting up a return value or side effect, the value after the attribute path specification must be a
      JSON-deserializable value (and strings must be in double quotes). Values that deserialize to `dict` objects will
      be special dictionaries whose keys can also be accessed as attributes. This is analogous to:

      .. code-block:: python

          mock_object.return_value = AttrDict({"id": 3, "name": "Hello, world"})

    * Line 6 demonstrates setting an exception as a side-effect. Instead of following the path specification with a
      JSON-deserializable value, you follow it with the keyword `exception` followed by either a `builtin` exception
      name or a `path.to.model:ExceptionName` for non-builtin exceptions. This is analogous to:

      .. code-block:: python

          mock_object.foo_attribute.return_value.bar_attribute.side_effect = IOError

    * Line 7 demonstrates deleting the `qux_attribute` attribute of `third_party_object.foo_attribute.return_value` so
      that `Mock` won't mock it. Any attempt by the underlying code to access `qux_attribute` will result in an
      `AttributeError`. This is analogous to:

      .. code-block:: python

          del mock_object.foo_attribute.return_value.qux_attribute

    This directive applies to the entire test case in which it is defined. The patch is started once, before any action
    cases run, and stopped once, after all action cases run.
    """  # noqa

    @classmethod
    def name(cls):
        return 'mock_result_for_test'

    @classmethod
    def supplies_additional_grammar_types(cls):
        return {
            'json': 'PLAIN_LANGUAGE',
            'instruction': "'exception' | 'delete'",
            'mock_path': "NAME (NAME | '.')*",
            'mock_target': "NAME (NAME | '.')*",
        }

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('mock') +
            ':' +
            _mock_target_syntax +
            ':' +
            _mock_path_syntax +
            ':' +
            Optional(oneOf(('exception', 'delete')))('instruction') +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        mock = _ensure_mock_in_target_and_return(test_case, parse_results.mock_target)
        _assemble_mock_path_result(mock, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class MockPathResultForActionDirective(ActionDirective):
    """
    Use this to patch a target with `unittest.Mock` and set up a return value or side effect for that mock or any of
    its attributes at any path level. This directive applies to the specific action case in which it is defined. The
    patch is started once, after any test-case-level patches (if applicable) are started and before before the action
    is called, and stopped once, after the action returns and before any test-case-level patches (if applicable) are
    stopped.

    For full documentation on how to use this directive, see the documentation for the test-case-level `mock`
    directive, with these revised examples::

        user_action: mock: example_service.actions.users.random: randint.return_value: 31
        user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "abc123"
        user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "def456"
        user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "ghi789"
        user_action: mock: example_service.actions.users.third_party_object: return_value: {"id": 3, "name": "Hello, world"}
        user_action: mock: example_service.actions.users.third_party_object: foo_attribute.return_value.bar_attribute.side_effect: exception IOError
        user_action: mock: example_service.actions.users.third_party_object: foo_attribute.return_value.qux_attribute: delete
    """  # noqa

    @classmethod
    def name(cls):
        return 'mock_result_for_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(MockPathResultForActionDirective, cls).get_full_grammar() +
            Literal('mock') +
            ':' +
            _mock_target_syntax +
            ':' +
            _mock_path_syntax +
            ':' +
            Optional(oneOf(('exception', 'delete')))('instruction') +
            VarValueGrammar
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        mock = _ensure_mock_in_target_and_return(action_case, parse_results.mock_target)
        _assemble_mock_path_result(mock, parse_results, file_name, line_number)

    def assert_test_case_action_results(*_, **__):
        pass


class MockAssertCalledTestPlanDirective(Directive):
    """
    Use this to patch a target with `unittest.Mock` and expect it to be called with certain arguments. For example, if
    your module named `example_service.actions.users` imported `random`, `uuid`, and `third_party_object`, you could
    mock those three imported items and expect function calls with the following::

        mock: example_service.actions.users.random: expect called randint: [[0, 999], {}]
        mock: example_service.actions.users.random: expect called randint: [[1000, 1999], {}]
        mock: example_service.actions.users.random: expect called randint: [[2000, 2999], {}]
        mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        mock: example_service.actions.users.third_party_object: expect called: [[], {"foo": 10382}]
        mock: example_service.actions.users.third_party_object: expect not called foo_attribute.save:

    Taking a look at each line in this example:

    * Lines 1 through 3 set up `random.randint` to expect to be called three times, the first time with arguments
      `0` and `999` and no keyword arguments, the second time with arguments `1000` and `1999` and no keyword arguments,
      and the third time with arguments `2000` and `2999` and no keyword arguments. This is analogous to:

      .. code-block:: python

          mock_random.rand_int.assert_has_calls([
              mock.call(0, 999),
              mock.call(1000, 1999),
              mock.call(2000, 2999),
          ])
          assert mock_random.rand_int.call_count == 3

    * Lines 4 through 6 set up `uuid.uuid4` to expect to be called three times, each time with no arguments or keyword
      arguments. Note that, even with no arguments, you must specify a two-element list whose first element is a list
      of args (in this case empty) and whose second element is a dictionary of kwargs (in this case empty) whose keys
      must be strings (double quotes). This is analogous to:

      .. code-block:: python

          mock_uuid.uuid4.assert_has_calls([mock.call(), mock.call(), mock.call()])
          assert mock_uuid.uuid4.call_count == 3

    * Line 7 sets up `third_party_object` to, itself, be called, with no arguments and with a single keyword argument
      `foo` having value `10382`. This is analogous to:

      .. code-block:: python

          mock_object.assert_has_calls([mock.call(foo=10382)])
          assert mock_object.call_count == 1

    * Line 8 sets up `third_party_object.foo_attribute.save` to expect to have *not* been called. This is analogous to:

      .. code-block:: python

          assert mock_object.foo_attribute.save.call_count == 0

    These expectations are checked at the end of the test case, after all actions have run. If any expectation is not
    met, the test fails with an `AssertionError`.
    """

    @classmethod
    def name(cls):
        return 'mock_assert_called_for_test'

    @classmethod
    def get_full_grammar(cls):
        return (
            Literal('mock') +
            ':' +
            _mock_target_syntax +
            ':' +
            Literal('expect') +
            Optional('not').setResultsName('not') +
            Literal('called') +
            Optional(_mock_path_syntax) +
            ':' +
            _json_syntax
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        mock = _ensure_mock_in_target_and_return(test_case, parse_results.mock_target)
        _assemble_mock_expectations(mock, parse_results, file_name, line_number)

    def set_up_test_case(self, test_case, test_fixture, **kwargs):
        _start_patches(test_case)

    def tear_down_test_case(self, test_case, test_fixture, **kwargs):
        # since we're at the end of the test case, just stop _all_ patches, in case action patches didn't get cleaned up
        unittest_mock.patch.stopall()

    def assert_test_case_results(self, test_action_results_dict, test_case, test_fixture, msg=None, **kwargs):
        _assert_mock_expectations(test_case)

    def assert_test_case_action_results(*_, **__):
        pass


class MockAssertCalledActionDirective(ActionDirective):
    """
    Use this to patch a target with `unittest.Mock` and expect it to be called with certain arguments. These
    expectations are checked at the end of the action case, after the action has run, before the next action runs, and
    before any test-case-level mock expectations are checked.

    For full documentation on how to use this directive, see the documentation for the test-case-level
    `mock ... expect` directive, with these revised examples::

        user_action: mock: example_service.actions.users.random: expect called randint: [[0, 999], {}]
        user_action: mock: example_service.actions.users.random: expect called randint: [[1000, 1999], {}]
        user_action: mock: example_service.actions.users.random: expect called randint: [[2000, 2999], {}]
        user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
        user_action: mock: example_service.actions.users.third_party_object: expect called: [[], {"foo": 10382}]
        user_action: mock: example_service.actions.users.third_party_object: expect not called foo_attribute.save:
    """

    @classmethod
    def name(cls):
        return 'mock_assert_called_for_action'

    @classmethod
    def get_full_grammar(cls):
        return (
            super(MockAssertCalledActionDirective, cls).get_full_grammar() +
            Literal('mock') +
            ':' +
            _mock_target_syntax +
            ':' +
            Literal('expect') +
            Optional('not').setResultsName('not') +
            Literal('called') +
            Optional(_mock_path_syntax) +
            ':' +
            _json_syntax
        )

    def ingest_from_parsed_test_fixture(self, action_case, test_case, parse_results, file_name, line_number):
        mock = _ensure_mock_in_target_and_return(action_case, parse_results.mock_target)
        _assemble_mock_expectations(mock, parse_results, file_name, line_number)

    def set_up_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        _start_patches(action_case)

    def tear_down_test_case_action(self, action_name, action_case, test_case, test_fixture, **kwargs):
        if 'mock_patches' in action_case:
            for mock_target, config in six.iteritems(action_case['mock_patches']):
                if 'magic_mock' in config:  # means the patch was started
                    # noinspection PyBroadException
                    try:
                        config['patcher'].stop()
                    except Exception:
                        sys.stderr.write('WARNING: Failed to stop patcher for {} due to error:\n'.format(mock_target))
                        sys.stderr.write('{}\n'.format(traceback.format_exc()))

    def assert_test_case_action_results(
        self,
        action_name,
        action_case,
        test_case,
        test_fixture,
        action_response,
        job_response,
        msg=None,
        **kwargs
    ):
        _assert_mock_expectations(action_case)


register_directive(MockAssertCalledTestPlanDirective)
register_directive(MockAssertCalledActionDirective)
register_directive(MockPathResultForTestPlanDirective)
register_directive(MockPathResultForActionDirective)
