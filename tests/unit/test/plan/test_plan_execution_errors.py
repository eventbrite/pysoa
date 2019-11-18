from __future__ import (
    absolute_import,
    unicode_literals,
)

import os
from typing import (
    Dict,
    List,
    Mapping,
    Optional,
    Type,
    cast,
)

from conformity.settings import SettingsData
import pytest
import six

from pysoa.common.types import ActionResponse
from pysoa.server.server import Server
from pysoa.server.types import ActionType
from pysoa.test.compatibility import mock
from pysoa.test.plan import ServicePlanTestCase
from pysoa.test.plan.errors import (
    FixtureLoadError,
    StatusError,
)
from pysoa.test.plan.grammar.directive import Directive


class _TestServiceServer(Server):
    service_name = 'test_service'
    action_class_map = {}  # type: Mapping[six.text_type, ActionType]


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


# noinspection PyUnresolvedReferences
class MockedTestCase(ServicePlanTestCase):
    server_class = _TestServiceServer
    server_settings = {}  # type: SettingsData

    add_error = mock.MagicMock()
    set_up_test_fixture = mock.MagicMock()
    tear_down_test_fixture = mock.MagicMock()
    set_up_test_case = mock.MagicMock()
    tear_down_test_case = mock.MagicMock()
    set_up_test_case_action = mock.MagicMock()
    tear_down_test_case_action = mock.MagicMock()
    _run_test_case = mock.MagicMock()

    setUpClass = mock.MagicMock()
    setUpClass.__func__ = ServicePlanTestCase.setUpClass.__func__  # type: ignore
    tearDownClass = mock.MagicMock()
    tearDownClass.__func__ = ServicePlanTestCase.tearDownClass.__func__  # type: ignore

    _all_directives = [cast(Type[Directive], mock.MagicMock()), ]

    @classmethod
    def reset(cls):
        cls._test_fixture_setup_called = {}  # type: ignore
        cls._test_fixture_setup_succeeded = {}  # type: ignore

        cls.add_error = mock.MagicMock()
        cls.set_up_test_fixture = mock.MagicMock()
        cls.tear_down_test_fixture = mock.MagicMock()
        cls.set_up_test_case = mock.MagicMock()
        cls.tear_down_test_case = mock.MagicMock()
        cls.set_up_test_case_action = mock.MagicMock()
        cls.tear_down_test_case_action = mock.MagicMock()
        cls._run_test_case = mock.MagicMock()

        cls._all_directives = [cast(Type[Directive], mock.MagicMock()), ]
        # Mock doesn't automatically mock methods that start with `assert`, so we have to do this
        cls._all_directives[0].return_value.assert_test_fixture_results = mock.MagicMock()  # type: ignore


# noinspection PyProtectedMember,PyMethodMayBeStatic
class TestInvalidFixturePaths(object):
    def setup_method(self):
        MockedTestCase.reset()

    def test_path_does_not_exist(self):
        class TestCase(ServicePlanTestCase):
            fixture_path = '/invalid/path'

        with pytest.raises(FixtureLoadError) as error_context:
            TestCase.get_fixture_file_names()

        assert 'path does not exist' in error_context.value.args[0]

    def test_path_has_no_fixtures(self):
        class TestCase(ServicePlanTestCase):
            fixture_path = os.path.dirname(__file__) + '/empty'

        with pytest.raises(FixtureLoadError) as error_context:
            TestCase.get_fixture_file_names()

        assert 'Could not find any fixture files' in error_context.value.args[0]

    def test_abnormal_fixture_tear_down_succeeded(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'my_fixture'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test._pytest_first_fixture_case = case_data  # type: ignore

        assert test_function.__doc__ == 'My test description'

        test.set_up_test_fixture.assert_not_called()
        test.tear_down_test_fixture.assert_not_called()
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

        test.setup_method()
        test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
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

        test.teardown_class()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_abnormal_fixture_tear_down_failed(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'your_fixture'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function(
            'Your test description',
            'your_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test._pytest_first_fixture_case = case_data  # type: ignore

        assert test_function.__doc__ == 'Your test description'

        test.setup_method()
        test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
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

        with pytest.raises(Error1):
            test.teardown_class()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_normal_fixture_tear_down(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'my_fixture'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        assert test_function.__doc__ == 'My test description'

        test.setup_method()
        test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        test.teardown_class()

        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)

        test.add_error.assert_not_called()

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_fixture_setup_failed(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'my_fixture'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function(
            'My test description',
            'my_fixture',
            test_case,
            test_fixture,
            test_fixture_results,
        )
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        assert test_function.__doc__ == 'My test description'

        test.set_up_test_fixture.side_effect = Error1()

        with pytest.raises(Error1):
            test.setup_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
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

        with pytest.raises(StatusError):
            test_function(test)

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_error_on_set_up_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test.tear_down_test_fixture.side_effect = Error3()

        with mock.patch('pysoa.test.server.PyTestServerTestCase.setup_method') as mock_setup_method, \
                mock.patch('pysoa.test.server.PyTestServerTestCase.teardown_method') as mock_teardown_method:
            mock_setup_method.side_effect = Error1()
            mock_teardown_method.side_effect = Error2()
            with pytest.raises(Error1):
                test.setup_method()
            with pytest.raises(Error2):
                test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
        test.set_up_test_case.assert_not_called()
        test.tear_down_test_case.assert_not_called()
        test.set_up_test_case_action.assert_not_called()
        test.tear_down_test_case_action.assert_not_called()
        test._run_test_case.assert_not_called()

        mock_dir = cast(mock.MagicMock, test._all_directives[0])
        mock_dir.return_value.set_up_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.assert_test_fixture_results.assert_not_called()
        mock_dir.return_value.tear_down_test_fixture.assert_called_once_with(test_fixture)
        mock_dir.return_value.set_up_test_case.assert_not_called()
        mock_dir.return_value.tear_down_test_case.assert_not_called()
        mock_dir.return_value.set_up_test_case_action.assert_not_called()
        mock_dir.return_value.tear_down_test_case_action.assert_not_called()

        assert test.add_error.call_count == 1

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_error_on_set_up_test_case_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test.set_up_test_case.side_effect = Error1()

        test.setup_method()
        with pytest.raises(Error1):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_error_on_run_test_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test._run_test_case.side_effect = Error1()

        test.setup_method()
        with pytest.raises(Error1):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_error_on_run_test_no_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test._run_test_case.side_effect = Error1()
        test.tear_down_test_case.side_effect = Error2()
        test.tear_down_test_fixture.side_effect = Error3()

        test.setup_method()
        with pytest.raises(Error1):
            test_function(test)
        with pytest.raises(Error3):
            test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.add_error.call_count == 1

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_error_on_run_test_no_different_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test._run_test_case.side_effect = Error4()
        test.tear_down_test_case.side_effect = KeyboardInterrupt()
        mock_dir.return_value.assert_test_fixture_results.side_effect = Error5()

        test.setup_method()
        with pytest.raises(Error4):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.add_error.call_count == 1

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_keyboard_error_on_tear_down_test_case_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test.tear_down_test_case.side_effect = KeyboardInterrupt()

        test.setup_method()
        with pytest.raises(KeyboardInterrupt):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_other_error_on_tear_down_test_case_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        test.tear_down_test_case.side_effect = Error2()
        mock_dir.return_value.assert_test_fixture_results.side_effect = Error5()

        test.setup_method()
        with pytest.raises(Error2):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.add_error.call_count == 1

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_keyboard_error_on_tear_down_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test.setup_method()
        test_function(test)
        with mock.patch('pysoa.test.server.PyTestServerTestCase.teardown_method') as mock_teardown_method:
            mock_teardown_method.side_effect = KeyboardInterrupt()
            with pytest.raises(KeyboardInterrupt):
                test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_keyboard_error_on_assert_test_fixture_results_no_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = KeyboardInterrupt()

        test.setup_method()
        with pytest.raises(KeyboardInterrupt):
            test_function(test)
        test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_assertion_error_on_assert_test_fixture_results_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = AssertionError()
        test.tear_down_test_fixture.side_effect = Error5()

        test.setup_method()
        with pytest.raises(AssertionError):
            test_function(test)
        with pytest.raises(Error5):
            test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.add_error.call_count == 0

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_other_error_on_assert_test_fixture_results_some_other_errors(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.assert_test_fixture_results.side_effect = Error3()
        mock_dir.return_value.tear_down_test_fixture.side_effect = Error4()

        test.setup_method()
        with pytest.raises(Error3):
            test_function(test)
        with pytest.raises(Error4):
            test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
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

        assert test.add_error.call_count == 0

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_keyboard_error_on_tear_down_test_fixture(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        test.tear_down_test_fixture.side_effect = KeyboardInterrupt()

        test.setup_method()
        test_function(test)
        with pytest.raises(KeyboardInterrupt):
            test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_called_once_with(test_fixture)
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0

    def test_other_error_on_tear_down_test_fixture(self):
        test_case = {'my': 'case'}
        test_fixture = [{'foo': 'bar'}]
        test_fixture_results = [{'baz': None}]  # type: List[Dict[six.text_type, Optional[ActionResponse]]]

        test = MockedTestCase()

        case_data = mock.MagicMock()
        case_data.fixture_name = 'bbb'
        case_data.test_fixture = test_fixture

        test_function = test._create_test_function('aaa', 'bbb', test_case, test_fixture, test_fixture_results)
        test_function._last_fixture_test = True  # type: ignore
        test._pytest_first_fixture_case = case_data  # type: ignore
        test._pytest_last_fixture_case = case_data  # type: ignore

        mock_dir = cast(mock.MagicMock, test._all_directives[0])

        mock_dir.return_value.tear_down_test_fixture.side_effect = Error1()

        test.setup_method()
        test_function(test)
        with pytest.raises(Error1):
            test.teardown_method()

        test.set_up_test_fixture.assert_called_once_with(test_fixture)
        test.tear_down_test_fixture.assert_not_called()
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

        assert test.setUpClass.call_count == 0
        assert test.tearDownClass.call_count == 0
