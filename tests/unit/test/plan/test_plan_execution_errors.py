from __future__ import (
    absolute_import,
    unicode_literals,
)

import os
from typing import (
    Dict,
    List,
    Optional,
    Type,
    cast,
)
import unittest

import six

from pysoa.common.types import ActionResponse
from pysoa.test.compatibility import mock
from pysoa.test.plan import ServicePlanTestCase
from pysoa.test.plan.errors import (
    FixtureLoadError,
    StatusError,
)
from pysoa.test.plan.grammar.directive import Directive


class Error1(BaseException):
    pass


class Error2(BaseException):
    pass


class Error3(BaseException):
    pass


class Error4(BaseException):
    pass


class Error5(BaseException):
    pass


class MockedTestCase(ServicePlanTestCase):
    add_error = mock.MagicMock()
    set_up_test_fixture = mock.MagicMock()
    tear_down_test_fixture = mock.MagicMock()
    setUp = mock.MagicMock()
    tearDown = mock.MagicMock()
    set_up_test_case = mock.MagicMock()
    tear_down_test_case = mock.MagicMock()
    set_up_test_case_action = mock.MagicMock()
    tear_down_test_case_action = mock.MagicMock()
    _run_test_case = mock.MagicMock()

    _all_directives = [cast(Type[Directive], mock.MagicMock()), ]

    def __init__(self):
        super(MockedTestCase, self).__init__('fake_test')

    def fake_test(self):
        """
        This is so that we can instantiate the class.
        """

    @classmethod
    def reset(cls, include_setup=True):
        if include_setup:
            if hasattr(cls, '_test_fixture_setup_called'):
                del cls._test_fixture_setup_called  # type: ignore
            if hasattr(cls, '_test_fixture_setup_succeeded'):
                del cls._test_fixture_setup_succeeded  # type: ignore

        cls.add_error = mock.MagicMock()
        cls.set_up_test_fixture = mock.MagicMock()
        cls.tear_down_test_fixture = mock.MagicMock()
        cls.setUp = mock.MagicMock()
        cls.tearDown = mock.MagicMock()
        cls.set_up_test_case = mock.MagicMock()
        cls.tear_down_test_case = mock.MagicMock()
        cls.set_up_test_case_action = mock.MagicMock()
        cls.tear_down_test_case_action = mock.MagicMock()
        cls._run_test_case = mock.MagicMock()

        cls._all_directives = [cast(Type[Directive], mock.MagicMock()), ]
        # Mock doesn't automatically mock methods that start with `assert`, so we have to do this
        cls._all_directives[0].return_value.assert_test_fixture_results = mock.MagicMock()  # type: ignore


class TestInvalidFixturePaths(unittest.TestCase):
    def setUp(self):
        MockedTestCase.reset()

    def test_path_does_not_exist(self):
        class TestCase(ServicePlanTestCase):
            fixture_path = '/invalid/path'

        with self.assertRaises(FixtureLoadError) as error_context:
            TestCase.get_fixture_file_names()

        self.assertIn('path does not exist', error_context.exception.args[0])

    def test_path_has_no_fixtures(self):
        class TestCase(ServicePlanTestCase):
            fixture_path = os.path.dirname(__file__) + '/empty'

        with self.assertRaises(FixtureLoadError) as error_context:
            TestCase.get_fixture_file_names()

        self.assertIn('Could not find any fixture files', error_context.exception.args[0])

    def test_abnormal_fixture_tear_down_succeeded(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )

        self.assertEqual('My test description', test_function.__doc__)

        test.set_up_test_fixture.assert_not_called()
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_not_called()
        test.tearDown.assert_not_called()
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_not_called()
        mock_dir.return_value.tear_down_test_fixture.assert_not_called()
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_not_called()
        mock_dir.return_value.tear_down_test_fixture.assert_not_called()
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.tearDownClass()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

    def test_abnormal_fixture_tear_down_failed(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function(
            'Your test description',
            'your_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )

        self.assertEqual('Your test description', test_function.__doc__)

        test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_not_called()
        mock_dir.return_value.tear_down_test_fixture.assert_not_called()
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.tear_down_test_fixture.side_effect = Error1()

        with self.assertRaises(Error1):
            test.tearDownClass()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

    def test_normal_fixture_tear_down(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test_function._last_fixture_test = True  # type: ignore

        self.assertEqual('My test description', test_function.__doc__)

        test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.tearDownClass()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

    def test_fixture_setup_failed(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test_function._last_fixture_test = True  # type: ignore

        self.assertEqual('My test description', test_function.__doc__)

        test.set_up_test_fixture.side_effect = Error1()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_not_called()
        test.tearDown.assert_not_called()
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_not_called()
        mock_dir.return_value.assert_test_fixture_results.assert_not_called()
        mock_dir.return_value.tear_down_test_fixture.assert_not_called()
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        with self.assertRaises(StatusError):
            test_function(test)

    def test_error_on_set_up_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.setUp.side_effect = Error1()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_error_on_set_up_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.setUp.side_effect = Error1()
        test.tearDown.side_effect = Error2()
        test.tear_down_test_fixture.side_effect = Error3()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        self.assertEqual(2, test.add_error.call_count)

    def test_error_on_set_up_different_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test.setUp.side_effect = Error3()
        test.tearDown.side_effect = KeyboardInterrupt()
        mock_dir.return_value.assert_test_fixture_results.side_effect = AssertionError()
        test.tear_down_test_fixture.side_effect = KeyboardInterrupt()

        with self.assertRaises(Error3):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.assertEqual(1, test.add_error.call_count)

    def test_error_on_set_up_test_case_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.set_up_test_case.side_effect = Error1()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()
        test.add_error.assert_not_called()

    def test_error_on_run_test_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test._run_test_case.side_effect = Error1()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_error_on_run_test_no_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test._run_test_case.side_effect = Error1()
        test.tear_down_test_case.side_effect = Error2()
        test.tear_down_test_fixture.side_effect = Error3()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        self.assertEqual(2, test.add_error.call_count)

    def test_error_on_run_test_no_different_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test._run_test_case.side_effect = Error4()
        test.tear_down_test_case.side_effect = KeyboardInterrupt()
        mock_dir.return_value.assert_test_fixture_results.side_effect = Error5()

        with self.assertRaises(Error4):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.assertEqual(1, test.add_error.call_count)

    def test_keyboard_error_on_tear_down_test_case_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.tear_down_test_case.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_other_error_on_tear_down_test_case_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test.tear_down_test_case.side_effect = Error2()
        mock_dir.return_value.assert_test_fixture_results.side_effect = Error5()

        with self.assertRaises(Error2):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.assertEqual(1, test.add_error.call_count)

    def test_keyboard_error_on_tear_down_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.tearDown.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_other_error_on_tear_down_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test.tearDown.side_effect = Error2()
        mock_dir.return_value.assert_test_fixture_results.side_effect = KeyboardInterrupt()

        with self.assertRaises(Error2):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_keyboard_error_on_assert_test_fixture_results_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_assertion_error_on_assert_test_fixture_results_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = AssertionError()
        test.tear_down_test_fixture.side_effect = Error5()

        with self.assertRaises(AssertionError):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.assertEqual(1, test.add_error.call_count)

    def test_other_error_on_assert_test_fixture_results_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = Error3()
        mock_dir.return_value.tear_down_test_fixture.side_effect = Error4()

        with self.assertRaises(Error3):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.assertEqual(1, test.add_error.call_count)

    def test_keyboard_error_on_tear_down_test_fixture(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        test.tear_down_test_fixture.side_effect = KeyboardInterrupt()

        with self.assertRaises(KeyboardInterrupt):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()

    def test_other_error_on_tear_down_test_fixture(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.tear_down_test_fixture.side_effect = Error1()

        with self.assertRaises(Error1):
            test_function(test)

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
        test.setUp.assert_called_once_with()
        test.tearDown.assert_called_once_with()
        test.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        test.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_called_once_with(test_case, test_fixture, test_fixture_results)

        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_called_once_with(
            test_fixture_results,
            test_fixture,
        )
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.tear_down_test_case.assert_called_once_with(test_case, test_fixture)
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        test.add_error.assert_not_called()
