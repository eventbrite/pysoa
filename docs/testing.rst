Testing with PySOA
==================

PySOA comes with several facilities for testing—both for testing services themselves and for testing code that interacts
with PySOA services. This document describes these libraries and techniques. As always, all strings in the examples
are unicode strings (the default in Python 3; use ``from __future__ import unicode_literals`` for Python 2).

.. contents:: Contents
   :depth: 3
   :backlinks: none


Using the ``ServerTestCase``
++++++++++++++++++++++++++++

The ``ServerTestCase`` is an extension of ``unittest.TestCase`` that has built-in tools for easily testing PySOA service
calls. When writing a PySOA service, there are likely many things for which you will want to write automated tests. If
you are strict about unit tests, you may simply instantiate your action classes and test the individual methods as pure
units of code. If you are less strict about this, or if you want to write integration tests for your service, the
``ServerTestCase`` makes it easy to locally configure your service and make service calls to it with minimal effort.


Setting Up a Test Case Class
****************************

The initial part of writing such tests is setting up your test case with your server class:

.. code-block:: python

    from pysoa.test.server import ServerTestCase

    from example_service.server import ExampleServer


    class TestMyAction(ServerTestCase):
        server_class = ExampleServer
        server_settings = {}


As simple as this code looks, it does a lot! Before each test method runs, it configures ``ExampleServer`` (your class
that extends ``pysoa.server.Server``) as a local service. It then configures a client (available in the test case class
as ``self.client``) to call that service locally.

If your service has special settings that need to be configured, you can set them up by customizing the
``server_settings`` class attribute; however, in most cases, all you need is an empty dict with no settings. If you do
not specify ``server_settings``, it will look for Django ``settings.SOA_SERVER_SETTINGS`` if you have
``ExampleServer.use_django`` set to ``True``, otherwise it will look for the environmental variable
``PYSOA_SETTINGS_MODULE`` and import and use the ``SOA_SERVER_SETTINGS`` constant in that module. If it can't find any
of these, every test in the test case will fail in ``setUp``. Whatever your settings source, the transport will be
overridden by the local transport for the purposes of the tests.

If you override the ``setUp`` method in your test case class, be sure to call ``super``; otherwise, your test class
will not set up properly.


Using Test Helper Methods
*************************

You can use ``self.call_action`` in test methods as a shortcut for ``self.client.call_action``, and it will
automatically provide the service name to ``self.client.call_action`` on your behalf.

This test class also provides the following extension assertion methods:

- ``assertActionRunsWithAndReturnErrors``: Pass it an action name, request body, and any request kwargs, and it will
  call the action, failing if no errors were encountered, and returning ``actions[0].errors`` otherwise.
- ``assertActionRunsWithFieldErrors``: Pass it an action name, request body, a dict of field name keys and values
  that are string error codes, lists of string error codes, or sets of string error codes, and any request kwargs, and
  it will call the action, failing unless all of the field errors passed in were encountered. It will allow and ignore
  any additional regular or field errors that were encountered but not expected without error.
- ``assertActionRunsWithOnlyFieldErrors``: The same as ``assertActionRunsWithFieldErrors``, except that it will also
  fail if any additional errors not expected are encountered.
- ``assertActionRunsWithErrorCodes``: Pass it an action name, request body, a single error code or list or set of error
  codes, and any request kwargs, and it will call the action, failing unless all of the non-field error codes passed in
  were encountered. It will allow and ignore any additional regular or field errors that were encountered but not
  expected without error.
- ``assertActionRunsWithOnlyErrorCodes``: The same as ``assertActionRunsWithErrorCodes``, except that it will also
  fail if any additional errors not expected are encountered.


Examples
********

Here is a full example using all the asserts:

.. code-block:: python

    class TestManageObjectActions(ServerTestCase):
        server_class = ExampleServer
        server_settings = {
            'service_name': 'example',
        }

        def test_one(self):
            errors = self.assertActionRunsWithAndReturnErrors('get_object', {})

            self.assertEqual(1, len(errors))
            self.assertEqual('FIELD_MISSING', errors[0].code)
            self.assertEqual('object_id', errors[0].field)

        def test_two(self):
            self.assertActionRunsWithFieldErrors('get_object', {}, {'object_id': 'FIELD_MISSING'})

        def test_three(self):
            self.assertActionRunsWithOnlyFieldErrors(
                'get_objects',
                {'object_id': '1234'},
                {'object_id': 'UNEXPECTED_FIELD', 'object_ids': {'FIELD_MISSING'}},
            )

        def test_four(self):
            self.assertActionRunsWithErrorCodes('get_object', {'object_id': '10'}, 'NOT_AUTHORIZED')

        def test_five(self):
            self.assertActionRunsWithOnlyErrorCodes(
                'create_object',
                {'name': 'test', 'color': 'green'},
                {'NOT_AUTHORIZED', 'DUPLICATE_OBJECT'},
            )


Using the ``stub_action`` Decorator & Context Manager
+++++++++++++++++++++++++++++++++++++++++++++++++++++

When writing integration tests or acceptance tests for code that calls PySOA services, real services should be wired
in so that your automation tests the behavior of the integration between your code and your services. However, when
writing unit tests for code that calls PySOA services, you should stub out those service calls so that the unit tests
only test the discrete units of code that call the services, instead of also testing the service behavior.

The ``stub_action`` tool is made specifically for this purpose. You can use this as a context manager or as a decorator,
but you can only decorate classes, instance methods, and class methods. Decorating static methods and functions will
cause it to munge the function argument order.


How it Works
************

If you are familiar with Python's ``mock.patch``, you already know much about how ``stub_action`` works.

As method a decorator, it stubs the service action in question and passes a stub action object to the test method as an
argument. As a class decorator, it does the same thing for every method in the class that starts with ``test_``.
Once the method invocation completes, the stub is cleaned up. If you have multiple stubs, multiple stub action objects
will be passed to the test method in the reverse order, so the stub listed first (furthest from the method) will be the
last argument, while the stub listed last (closest to the method) will be the first argument. If you mix ``stub_action``
with one or more ``mock.patch`` decorators, the argument order will follow the same mixed order of all of the
decorators.

As a context manager, ``with stub_action(...) as stub_xx_action:`` stubs the service action in question for the duration
of the given context, returning the stub action object for use within and following the ``with`` block, and cleaning up
the stub once the ``with`` block has terminated.

You can use multiple ``stub_action`` for multiple actions within the same service or for multiple actions across
multiple services. You can not use ``stub_action`` multiple times for the same service and action on the same method or
within the same context manager—you can, instead, expect and assert multiple calls on a single action with a single
use of ``stub_action`` as shown in the following examples.

``stub_action`` only affects the specific action on the specific service for which it is called. Any other actions
on the same service will still be called directly (or raise an error if the real service is not actually configured
in the test process), and any other actions on other services will still be called directly (or raise an error if
the real service is not configured).


Calling ``stub_action``
***********************

``stub_action`` has five potential arguments. Only the first two are required:

- ``service``: The name of the service on which this action will be called
- ``action``: The name of the action to stub
- ``body``: A dictionary containing the response body that the stubbed action should return (the same schema that
  would normally be returned from the action class's ``run`` method).
- ``errors``: A list of SOA errors that should be raised, where each error is a dict with at least ``code`` and
  ``message`` keys and optionally a ``field`` for field errors.
- ``side_effect``: A function, an exception class or instance, or an iterable. It behaves exactly like
  ``mock.MagicMock.side_effect``.

Instead of providing ``body`` and/or ``errors`` to ``stub_action``, you can manipulate the action stub object passed
to the test method (or returned from the context manager) to tell it to return certain values or have certain side
effects. The action stub object actually extends ``mock.MagicMock``, so you may already be very familiar with how it
works.

Given an action stub object ``stub_xx_action``, you can set ``stub_xx_action.return_value`` to control what the action
returns (this is equivalent to the ``body`` argument to ``stub_action``). Alternatively, you can set
``stub_xx_action.side_effect`` to raise SOA errors, provide different behavior for each of multiple expected calls, or
exert more control over how the stub behaves. ``side_effect`` can be a single value of any of the following or a
list/tuple (for multiple calls) where each value is any of the following:

``side_effect`` is useful for raising exceptions or dynamically changing return values. The function is called with the
same arguments as the mock, and unless it returns DEFAULT, the return value of this function is used as the return
value. Alternatively ``side_effect`` can be an exception class or instance. In this case the exception will be raised
when the mock is called. If ``side_effect`` is an iterable then each call to the mock will return the next value from
the iterable.

- A response body dict (same as the ``body`` argument to ``stub_action``)
- An instance of ``ActionError`` with one or more SOA errors configured
- A callable, which should accept one argument (which will be the request body dict) and should either return a
  response body dict or raise an ``ActionError``.


Making ``stub_action`` Assertions
*********************************

At the end of your test method, you will likely want to assert certain expectations about how a stubbed action was
called, such as whether it was called, how many times it was called, and with what request body(ies) contents it was
called. There are numerous ways to do this.

Because it extends ``mock.MagicMock``, you can use techniques like ``stub_xx_action.called``,
``stub_xx_action.call_count``, ``stub_xx_action.assert_called_once()``,
``stub_xx_action.assert_called_once_with({...request body dict...})``, and
``stub_xx_action.assert_has_calls(mock.call({...request body dict...}), mock.call({...}), ...)``.

Some PySOA-specific convenience properties are also defined. ``stub_xx_action.call_body`` will hold the request body
dict for the most recent call to the stubbed action, and is most useful for when you're expecting a single call.
Alternatively, ``stub_xx_action.call_bodies`` holds a list of all request body dicts for all calls to the stubbed
action in the order in which they were made. This is helpful for when you are expecting multiple calls to the same
action and want to assert their different values.


Examples
********

The sample test case below demonstrates the many ways that you can use ``stub_action``:

.. code-block:: python

    @stub_action('user', 'get_user', body={'user': {'id': 1234, 'username': 'John', 'email': 'john@example.org'}})
    class TestSomeCode(unittest.TestCase):
        """
        This class is decorated to stub an action that the tested code ends up calling for all or most of these tests.
        """

        def test_simple_user_helper(self, stub_get_user):
            # This test uses only the class-level stub
            user = UserHelper().get_user_from_service(user_id=5678)

            # Some of these assertions are redundant, giving you options based on your preferences. You would typically
            # not use all of them on a single action stub.
            self.assertTrue(stub_get_user.called)
            self.assertEqual(1, stub_get_user.call_count)
            self.assertEqual({'id': 5678}, stub_get_user.call_body)
            self.assertEqual(({'id': 5678}, ), stub_get_user.call_bodies)
            stub_get_user.assert_called_once_with({'id': 5678})
            stub_get_user.assert_has_calls(
                mock.call({'id': 5678}),
            )

        @stub_action('settings', 'get_user_setting')
        def test_complex_user_helper(self, stub_get_user_setting, stub_get_user):
            # You can combine class and method decorators. As with `mock.patch`, the order of the arguments is the
            # reverse of that which you would expect. You can also combine class and/or function stub decorators with
            # `mock.patch` decorators, and the order of the various stubs and mocks will likewise follow the order
            # they are mixed together.

            # Instead of passing a body or errors to the stub decorator or context manager, you can add it to the
            # stub after creation (but before use). Since action stubs extend `MagicMock`, you can use
            # `return_value` (it should be the response body dict) or `side_effect` (it should be ActionError(s),
            # response body dict(s), or callables). We use `side_effect` here to demonstrate expecting multiple calls.

            stub_get_user_setting.side_effect = (
                {'value': 'This is the first setting value response'},
                {'value': 'This is the second setting value response'},
                ActionError(errors=[Error(code='NO_SUCH_SETTING', message='The setting does not exist')]),
            )

            settings = UserHelper().get_user_settings(user_id=1234)

            self.assertEqual(
                {
                    'setting1', 'This is the first setting value response',
                    'setting2', 'This is the second setting value response',
                },
                settings,
            )

            self.assertEqual(3, stub_get_user_setting.call_count)
            self.assertEqual(
                (
                    {'user_id': 1234, 'setting_id': 'setting1'},
                    {'user_id': 1234, 'setting_id': 'setting2'},
                    {'user_id': 1234, 'setting_id': 'setting3'}
                ),
                stub_get_user_setting.call_bodies,
            )

            stub_user.assert_called_once_with({'id': 1234})

        def test_another_user_helper_with_context_manager(self, stub_get_user):
            # Using a context manager is intuitive and works essentially the same as using a decorator

            with stub_action('payroll', 'get_salary') as stub_get_salary:
                stub_get_salary.return_value = {'salary': 75950}

                salary = UserHelper().get_user_salary(user_id=1234)

            self.assertEqual(75950, salary)

            self.assertEqual(1, stub_get_salary.call_count)
            self.assertEqual({'user_id': 1234}, stub_get_salary.call_body)

            stub_user.assert_called_once_with({'id': 1234})

        def test_that_an_action_fails_with_inline_errors(self, stub_get_user):
            # Instead of using `side_effect` and `ActionError`, you can inline errors in the `stub_action`. The `field`
            # field in the dict is optional, and should only be used for errors that are field-validation errors.

            with stub_action('payroll', 'set_salary', errors=[
                {'code': 'NOT_AUTHORIZED', 'field': 'user_id', 'message': 'You are not authorized to update this user'},
            ]) as stub_set_salary, \
                self.assertRaises(NotAuthorizedToDoThatError):
                    salary = UserHelper().set_user_salary(user_id=1234, salary=88400)

            self.assertEqual(1, stub_set_salary.call_count)
            self.assertEqual({'user_id': 1234, 'salary': 88400}, stub_set_salary.call_body)

            stub_user.assert_called_once_with({'id': 1234})


Configuring a Stub Server & Client
++++++++++++++++++++++++++++++++++

Sometimes, during testing, you need to configure an entire stub service with very basic action responses to handle
widespread usage. For example, let's say you have some type of analytics service that is called to record user
analytics for just about every feature on your website. Adding ``stub_action`` to every unit test case class in your
codebase can quickly become tiresome.

An easier solution for this is to configure a PySOA ``StubServer``, ``StubClientTransport``, and ``StubClient`` (all in
``pysoa.test.stub_service``). The default polymorphic server and client classes make this extremely easy. The following
config dict can be passed like any normal configuration as the ``config`` argument to a new ``Client``. You can put
multiple services in the dict, and they do not have to all be stub services, so you can mix in a stub configuration
with your real configurations if you so wish.

.. code-block:: python

    SOA_CLIENT_SETTINGS = {
        ...
        'analytics': {
            'transport': {
                'path': 'pysoa.test.stub_service:StubClientTransport',
                'kwargs': {
                    'action_map': {
                        'record_analytic': {'body': {'success': True}},
                        'record_analytics': {'body': {'success': True}},
                    },
                },
            },
        },
        ...
    }


The ``action_map`` contains a dict of action names to action responses. It can contain either a response body dict
``body`` key or an error list ``errors`` key with the same semantics as the ``body`` and ``errors`` arguments to
``stub_action``, respectively. You won't be able to make assertions on the calls made (or not made) to these stubbed
actions.

As with any normal client settings, ``stub_action`` will also override ``StubClient`` settings, so you can use these
settings for handling most tests but still use ``stub_action('analytics', 'record_analytic', ...)`` for testing
specific behavior for which you need to control expectations and make assertions.


.. DO NOT EDIT THE CONTENTS BETWEEN THE FOLLOWING TWO "BEGIN" and "END" comments

.. BEGIN AUTO-GENERATED TEST PLAN DOCUMENTATION

PySOA Test Plans
++++++++++++++++

Another option for testing PySOA services is to use its test plan system. Test plans extend
``pysoa.test.plan:ServicePlanTestCase`` and define a collection of plain text fixture files (with extension ``.pysoa``)
that use a specialized syntax for describing test cases that call actions on your service.

To best understand PySOA test plans and this documentation, you'll need to understand a little bit of nomenclature:

- **Test Plan**: A class that extends ``pysoa.test.plan:ServicePlanTestCase`` and declares a directory in which test
  fixtures can be discovered for that test plan. If you want, you can have a single test plan for all of the test
  fixtures in your service. You can also have multiple test plans, each with one or more fixtures. The advantage of
  using multiple test plans is that each test plan class can have unique setup activities.
- **Test Fixture**: A ``.pysoa`` file containing one or more test cases defined using the PySOA Test Plan syntax. A
  test fixture's name is the test fixture file name absent the ``.pysoa`` extension and any directories.
- **Test Case**: A individual test case within a given test fixture. Each test case must have a name (letters, numbers,
  and underscores, only) and a description (a natural language sentence describing its purpose). A test case must have
  one or more action cases.
- **Action Case**: An individual call to a service action within a test case. Each action case has an associated set of
  inputs used to make the action call and expectations used to assert the results of the action call.


Running Test Plans
******************

PySOA test plans are collected and executed with a PyTest plugin, which is not installed by default. To enable this
plugin, you need to add ``pysoa[pytest]`` to your test requirements. Example:

.. code-block:: python

    tests_require = [
        'pysoa[pytest]',
        ...
    ]

Once you do this and install your testing dependencies, you will be able to run your service's test plans. Without
this, the presence of test plans in your service will result in errors during testing.

By default, all normal tests and test plan tests will run when you invoke ``pytest`` without arguments. If you pass a
directory to ``pytest``, it will run all normal tests and test plan tests in that directory. (NOTE: For the purposes
of directory collection, test plans reside in the test case class that declares them.) You can also easily filter the
tests fixtures and test cases that are run using the ``pytest`` arguments::

    # This will match all fixture AND non-fixture test cases with the name: get_user
    pytest -k get_user
    # This will match only fixture test cases with the name: get_user
    pytest --pysoa-test-case get_user
    # This will match only fixture test cases with names matching the regular expression ^get\_user.*
    pytest --pysoa-test-case-regex 'get\_user.*'
    # This will match only test cases within test fixtures with the name: user_actions
    pytest --pysoa-fixture user_actions
    # This will match only test cases named get_user within test fixtures named user_actions
    pytest --pysoa-fixture user_actions --pysoa-test-case get_user

Note that ``--pysoa-test-case`` and ``--pysoa-test-case-regex`` are mutually exclusive arguments. Use ``pytest --help``
to get more information about available plugin arguments.


Creating a Test Plan with ``ServicePlanTestCase``
*************************************************

In order to create test plans, the first thing you need to do is create a test case class that extends
``pysoa.test.plan:ServicePlanTestCase``. This class extends ``ServerTestCase`` (see `Using the ServerTestCase`_),
so you need to define the same ``server_class`` and ``server_settings`` attributes. Additionally, you need to define
either ``fixture_path`` or ``custom_fixtures``. You can also optionally specify ``model_constants``, which is used to
provide stock values for variable substitution (more on that later). Here are two possible examples:

.. code-block:: python

    import os

    from pysoa.test.plan import ServicePlanTestCase

    from user_service.server import Server


    class UserServiceFixtures(ServicePlanTestCase):
        server_class = Server
        server_settings = {}
        fixture_path = os.path.dirname(__file__) + '/service_fixtures'


    class ExtraServiceFixtures(ServicePlanTestCase):
        server_class = Server
        server_settings = {}
        custom_fixtures = (
            os.path.dirname(__file__) + '/extra_fixtures/special_actions_1.pysoa',
            os.path.dirname(__file__) + '/extra_fixtures/special_actions_2.pysoa',
        )
        model_constants = {
            'test_users': [
                {'id': '1838', 'username': 'john.smith'},
                {'id': '1792', 'username': 'jane.sanders'},
            ],
        }


``ServicePlanTestCase`` provides a number of hooks that you can use to set up and tear down plans, fixtures, test
cases, and action cases. To learn more about these hooks, see the docstrings in ``ServicePlanTestCase`` for the
following methods. In each case, if you override the hook, you must call ``super`` as the first line in your hook.

- ``setUpClass``
- ``set_up_test_fixture``
- ``setUp``
- ``set_up_test_case``
- ``set_up_test_case_action``
- ``tear_down_test_case_action``
- ``tear_don_test_case``
- ``tearDown``
- ``tear_down_test_fixture``
- ``tearDownClass``


Writing a Test Fixture
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

    NEWLINE: [\n]
    ALPHA: [a-zA-Z]+
    NUM: [0-9]+
    ALPHANUM: [a-zA-Z0-9]+
    NAME: ALPHA (ALPHANUM | '_')*
    HYPHENATED_NAME: NAME (NAME | '-')*
    PLAIN_LANGUAGE: ~NEWLINE

    action: NAME
    action_index: NUM
    comment: PLAIN_LANGUAGE
    data_type: 'base64_bytes' | 'bool' | 'bytes' | 'date' | 'datetime' | 'decimal' | 'emptydict' | 'emptylist' |
        'emptystr' | 'encoded_ascii' | 'encoded_unicode' | 'float' | 'int' | 'none' | 'None' | 'not regex' | 'regex' |
        'str' | 'time'
    description: PLAIN_LANGUAGE
    error_code: NAME
    error_message: PLAIN_LANGUAGE
    field_name: HYPHENATED_NAME (HYPHENATED_NAME | '.')*
    instruction: 'exception' | 'delete'
    job_slot: 'context' | 'control'
    json: PLAIN_LANGUAGE
    mock_path: NAME (NAME | '.')*
    mock_target: NAME (NAME | '.')*
    name: NAME
    reason: PLAIN_LANGUAGE
    value: PLAIN_LANGUAGE
    variable_name: ALPHANUM (ALPHANUM | [-_.{}])*

    fixture_comment: '#' comment
    test_name: 'test name' ':' name
    test_description: 'test description' ':' description
    test_skip: 'test skip' ['global'] ':' reason
    input: action ['.' action_index] ':' ['global'] ['job' job_slot] 'input' [data_type] ':' variable_name ':' value
    expect_error_field_message: action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error'
        ':' 'code' '=' error_code ',' 'field' '=' field_name ',' 'message' '=' error_message
    expect_error_message: action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':'
        'code' '=' error_code ',' 'message' '=' error_message
    expect_error_field: action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':'
        'code' '=' error_code ',' 'field' '=' field_name
    expect_error: action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':' 'code'
        '=' error_code
    expect_no_errors: action ['.' action_index] ':' ['global'] 'expect' ':' 'no errors'
    expect_value: action ['.' action_index] ':' ['global'] 'expect' [data_type] ':' ['not'] 'attribute value' ':'
        variable_name ':' value
    expect_any_value: action ['.' action_index] ':' ['global'] 'expect' 'any' [data_type] ':' 'attribute value' ':'
        variable_name [ ':']
    expect_none: action ['.' action_index] ':' ['global'] 'expect' 'NONE' ':' 'attribute value' ':' variable_name [ ':']
    expect_not_present: action ['.' action_index] ':' ['global'] 'expect not present' ':' 'attribute value' ':'
        variable_name [ ':']
    mock_assert_called_for_test: 'mock' ':' mock_target ':' 'expect' ['not'] 'called' [mock_path] ':' json
    mock_assert_called_for_action: action ['.' action_index] ':' ['global'] 'mock' ':' mock_target ':' 'expect' ['not']
        'called' [mock_path] ':' json
    mock_result_for_test: 'mock' ':' mock_target ':' mock_path ':' [exception | delete] value
    mock_result_for_action: action ['.' action_index] ':' ['global'] 'mock' ':' mock_target ':' mock_path ':'
        [exception | delete] value
    stub_action_body_for_test: 'stub action' ':' stub_service ':' stub_action ':' 'body' [data_type] ':' variable_name
        ':' value
    stub_action_body_for_action: action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':'
        stub_action ':' 'body' [data_type] ':' variable_name ':' value
    stub_action_error_for_test: 'stub action' ':' stub_service ':' stub_action ':' 'error' ':' 'code' '=' error_code
        ',' 'field' '=' field_name ',' 'message' '=' error_message
    stub_action_error_for_action: action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':'
        stub_action ':' 'error' ':' 'code' '=' error_code ',' 'field' '=' field_name ',' 'message' '=' error_message
    stub_action_called_for_test: 'stub action' ':' stub_service ':' stub_action ':' 'expect' ['not'] 'called' ((':') |
        ([data_type] ':' variable_name ':' value))
    stub_action_called_for_action: action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':'
        stub_action ':' 'expect' ['not'] 'called' ((':') | ([data_type] ':' variable_name ':' value))
    freeze_time_test: 'freeze time' ':' value
    freeze_time_action: action ['.' action_index] ':' ['global'] 'freeze time' ':' value

    global_directive: fixture_comment | test_skip | input | expect_error_field_message | expect_error_message |
        expect_error_field | expect_error | expect_no_errors | expect_value | expect_any_value | expect_none |
        expect_not_present | mock_assert_called_for_action | mock_result_for_action | stub_action_body_for_action |
        stub_action_error_for_action | stub_action_called_for_action | freeze_time_action

    test_directive: fixture_comment | test_skip | input | expect_error_field_message | expect_error_message |
        expect_error_field | expect_error | expect_no_errors | expect_value | expect_any_value | expect_none |
        expect_not_present | mock_assert_called_for_test | mock_assert_called_for_action | mock_result_for_test |
        mock_result_for_action | stub_action_body_for_test | stub_action_body_for_action | stub_action_error_for_test |
        stub_action_error_for_action | stub_action_called_for_test | stub_action_called_for_action | freeze_time_test |
        freeze_time_action

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

- ``base64_bytes``: Same as ``bytes``, except the value in the fixture directive is base64-encoded and should be
  decoded before use
- ``bool``: A boolean
- ``bytes``: A byte array, equivalent to ``bytes`` in Python 3 and ``str`` in Python 3
- ``date``: A ``datetime.date`` object
- ``datetime``: A ``datetime.datetime`` object
- ``decimal``: A ``decimal.Decimal`` object
- ``emptydict``: A zero-length dict (``{}``)
- ``emptylist``: A zero-length list (``[]``)
- ``emptystr``: A zero-length unicode string
- ``encoded_ascii``: A should-be-unicode string, except the value in the fixture directive has ASCII escape sequences
  that should be decoded before use
- ``encoded_unicode``: A unicode string, except the value in the fixture directive has Unicode escape sequences that
  should be decoded before use
- ``float``: A floating-point decimal
- ``int``: An integer, equivalent to a Python 3 ``int`` in either Python 2 or 3
- ``none``: ``None``
- ``None``: ``None``
- ``not regex``: Used for expectations only, the string value must *not* match this regular expression
- ``regex``: Used for expectations only, the string value must match this regular expression
- ``str``: A unicode string, equivalent to ``str`` in Python 3 and ``unicode`` in Python 2
- ``time``: A ``datetime.time`` object


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


Fixture Comment Directive
~~~~~~~~~~~~~~~~~~~~~~~~~

All lines that start with ``#`` are comments.

(from: ``pysoa.test.plan.grammar.directives.plans``)

Syntax::

    '#' comment


Test Name Directive
~~~~~~~~~~~~~~~~~~~

The (required) name of the test, which must be a valid method name in Python syntax.

(from: ``pysoa.test.plan.grammar.directives.plans``)

Syntax::

    'test name' ':' name


Test Description Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~

The (required) description for the test, which can be a regular, plain-language sentence.

(from: ``pysoa.test.plan.grammar.directives.plans``)

Syntax::

    'test description' ':' description


Test Skip Directive
~~~~~~~~~~~~~~~~~~~

Use this directive to skip a test or, with ``global``, to skip all tests in the entire fixture

(from: ``pysoa.test.plan.grammar.directives.plans``)

Syntax::

    'test skip' ['global'] ':' reason


Input Directive
~~~~~~~~~~~~~~~

Set inputs that will be sent for an action in the service request.

Using ``job control`` will put the value in the job control header instead of the action request.

Using ``job context`` will put the value in the job context header instead of the action request.

(from: ``pysoa.test.plan.grammar.directives.inputs``)

Syntax::

    action ['.' action_index] ':' ['global'] ['job' job_slot] 'input' [data_type] ':' variable_name ':' value


Expect Error Field Message Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
this code, field, *and* message will fulfill this expectation.

If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
error has this code, field, *and* message, this expectation will pass.

If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
each error case, you must use one or the other.

If ``job`` is used, then the job response will be examined for the error instead of the action response.

(from: ``pysoa.test.plan.grammar.directives.expects_errors``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':' 'code' '=' error_code
        ',' 'field' '=' field_name ',' 'message' '=' error_message


Expect Error Message Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
this code *and* message, whether or not it has a field value, will fulfill this expectation.

If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
error has this code *and* message (even if some errors have this code and other errors have this message), this
expectation will pass.

If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
each error case, you must use one or the other.

If ``job`` is used, then the job response will be examined for the error instead of the action response.

(from: ``pysoa.test.plan.grammar.directives.expects_errors``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':' 'code' '=' error_code
        ',' 'message' '=' error_message


Expect Error Field Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
this code *and* field, whether or not it has a message value, will fulfill this expectation.

If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
error has this code *and* field (even if some errors have this code and other errors have this field), this
expectation will pass.

If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
each error case, you must use one or the other.

If ``job`` is used, then the job response will be examined for the error instead of the action response.

(from: ``pysoa.test.plan.grammar.directives.expects_errors``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':' 'code' '=' error_code
        ',' 'field' '=' field_name


Expect Error Directive
~~~~~~~~~~~~~~~~~~~~~~

Set expectations that specific errors will (or will not) be in the service response. Any error that that matches
this code, whether or not it has a field or message, will fulfill this expectation.

If ``not`` is used, the absence of the error will be asserted (it negates the expectation exactly). As long as no
error has this code, this expectation will pass.

If ``exact`` is used, then all of the errors you define must match all of the errors in your response, and your
response cannot have any non-matching extra errors. ``exact`` and non-``exact`` are mutually-exclusive
expectations: an action case that has a mixture of ``exact`` and non-``exact`` error expectations will fail. For
each error case, you must use one or the other.

If ``job`` is used, then the job response will be examined for the error instead of the action response.

(from: ``pysoa.test.plan.grammar.directives.expects_errors``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' ':' ['not'] ['exact'] ['job'] 'error' ':' 'code' '=' error_code


Expect No Errors Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~

Expect that no errors are reported back in the service call response. Any error in either the job response or the
action response will cause this expectation to fail.

(from: ``pysoa.test.plan.grammar.directives.expects_errors``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' ':' 'no errors'


Expect Value Directive
~~~~~~~~~~~~~~~~~~~~~~

Set expectations for values to be in the service call response.

Using the ``not`` qualifier in the test will check to make sure that the field has any value other than the one
specified.

(from: ``pysoa.test.plan.grammar.directives.expects_values``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' [data_type] ':' ['not'] 'attribute value' ':' variable_name ':'
        value


Expect Any Value Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~

Set expectations for values to be in the service call response where any value for the given data type will be
accepted.

(from: ``pysoa.test.plan.grammar.directives.expects_values``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' 'any' [data_type] ':' 'attribute value' ':' variable_name [ ':']


Expect None Directive
~~~~~~~~~~~~~~~~~~~~~

Set expectations for values to be in the service call response where ``None`` value is expected.

(from: ``pysoa.test.plan.grammar.directives.expects_values``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect' 'NONE' ':' 'attribute value' ':' variable_name [ ':']


Expect Not Present Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Set expectation that the given field will not be present (even as a key) in the response.

(from: ``pysoa.test.plan.grammar.directives.expects_values``)

Syntax::

    action ['.' action_index] ':' ['global'] 'expect not present' ':' 'attribute value' ':' variable_name [ ':']


Mock Assert Called For Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this to patch a target with ``unittest.Mock`` and expect it to be called with certain arguments. For example, if
your module named ``example_service.actions.users`` imported ``random``, ``uuid``, and ``third_party_object``, you could
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

* Lines 1 through 3 set up ``random.randint`` to expect to be called three times, the first time with arguments
  ``0`` and ``999`` and no keyword arguments, the second time with arguments ``1000`` and ``1999`` and no keyword arguments,
  and the third time with arguments ``2000`` and ``2999`` and no keyword arguments. This is analogous to:

  .. code-block:: python

      mock_random.rand_int.assert_has_calls([
          mock.call(0, 999),
          mock.call(1000, 1999),
          mock.call(2000, 2999),
      ])
      assert mock_random.rand_int.call_count == 3

* Lines 4 through 6 set up ``uuid.uuid4`` to expect to be called three times, each time with no arguments or keyword
  arguments. Note that, even with no arguments, you must specify a two-element list whose first element is a list
  of args (in this case empty) and whose second element is a dictionary of kwargs (in this case empty) whose keys
  must be strings (double quotes). This is analogous to:

  .. code-block:: python

      mock_uuid.uuid4.assert_has_calls([mock.call(), mock.call(), mock.call()])
      assert mock_uuid.uuid4.call_count == 3

* Line 7 sets up ``third_party_object`` to, itself, be called, with no arguments and with a single keyword argument
  ``foo`` having value ``10382``. This is analogous to:

  .. code-block:: python

      mock_object.assert_has_calls([mock.call(foo=10382)])
      assert mock_object.call_count == 1

* Line 8 sets up ``third_party_object.foo_attribute.save`` to expect to have *not* been called. This is analogous to:

  .. code-block:: python

      assert mock_object.foo_attribute.save.call_count == 0

These expectations are checked at the end of the test case, after all actions have run. If any expectation is not
met, the test fails with an ``AssertionError``.

(from: ``pysoa.test.plan.grammar.directives.mock``)

Syntax::

    'mock' ':' mock_target ':' 'expect' ['not'] 'called' [mock_path] ':' json


Mock Assert Called For Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this to patch a target with ``unittest.Mock`` and expect it to be called with certain arguments. These
expectations are checked at the end of the action case, after the action has run, before the next action runs, and
before any test-case-level mock expectations are checked.

For full documentation on how to use this directive, see the documentation for the test-case-level
``mock ... expect`` directive, with these revised examples::

    user_action: mock: example_service.actions.users.random: expect called randint: [[0, 999], {}]
    user_action: mock: example_service.actions.users.random: expect called randint: [[1000, 1999], {}]
    user_action: mock: example_service.actions.users.random: expect called randint: [[2000, 2999], {}]
    user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
    user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
    user_action: mock: example_service.actions.users.uuid: expect called uuid4: [[], {}]
    user_action: mock: example_service.actions.users.third_party_object: expect called: [[], {"foo": 10382}]
    user_action: mock: example_service.actions.users.third_party_object: expect not called foo_attribute.save:

(from: ``pysoa.test.plan.grammar.directives.mock``)

Syntax::

    action ['.' action_index] ':' ['global'] 'mock' ':' mock_target ':' 'expect' ['not'] 'called' [mock_path] ':' json


Mock Result For Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this to patch a target with ``unittest.Mock`` and set up a return value or side effect for that mock or any of
its attributes at any path level. For example, if your module named ``example_service.actions.users`` imported
``random``, ``uuid``, and ``third_party_object``, you could mock those three imported items using the following potential
directives::

    mock: example_service.actions.users.random: randint.return_value: 31
    mock: example_service.actions.users.uuid: uuid4.side_effect: "abc123"
    mock: example_service.actions.users.uuid: uuid4.side_effect: "def456"
    mock: example_service.actions.users.uuid: uuid4.side_effect: "ghi789"
    mock: example_service.actions.users.third_party_object: return_value: {"id": 3, "name": "Hello, world"}
    mock: example_service.actions.users.third_party_object: foo_attribute.return_value.bar_attribute.side_effect: exception IOError
    mock: example_service.actions.users.third_party_object: foo_attribute.return_value.qux_attribute: delete

Taking a look at each line in this example:

* Line 1 sets up ``random.randint`` to return the value 31. It will return the value 31 every time it is called, no
  matter how many times this is. This is analogous to:

  .. code-block:: python

      mock_random.randint.return_value = 31

* Lines 2 through 4 set up ``uuid.uuid4`` to return the strings "abc123", "def456", and "ghi789," in that order.
  Using ``side_effect`` in this manner, ``uuid.uuid4`` cannot be called more than three times during the test, per
  standard ``Mock`` behavior. You must use ``side_effect`` in this order if you wish to specify multiple different
  return values. This is analogous to:

  .. code-block:: python

      mock_uuid.uuid4.side_effect = ("abc123", "def456", "ghi789")

* Line 5 sets up ``third_party_object`` to, when called, return the object ``{"id": 3, "name": "Hello, world"}``. Note
  that, when setting up a return value or side effect, the value after the attribute path specification must be a
  JSON-deserializable value (and strings must be in double quotes). Values that deserialize to ``dict`` objects will
  be special dictionaries whose keys can also be accessed as attributes. This is analogous to:

  .. code-block:: python

      mock_object.return_value = AttrDict({"id": 3, "name": "Hello, world"})

* Line 6 demonstrates setting an exception as a side-effect. Instead of following the path specification with a
  JSON-deserializable value, you follow it with the keyword ``exception`` followed by either a ``builtin`` exception
  name or a ``path.to.model:ExceptionName`` for non-builtin exceptions. This is analogous to:

  .. code-block:: python

      mock_object.foo_attribute.return_value.bar_attribute.side_effect = IOError

* Line 7 demonstrates deleting the ``qux_attribute`` attribute of ``third_party_object.foo_attribute.return_value`` so
  that ``Mock`` won't mock it. Any attempt by the underlying code to access ``qux_attribute`` will result in an
  ``AttributeError``. This is analogous to:

  .. code-block:: python

      del mock_object.foo_attribute.return_value.qux_attribute

This directive applies to the entire test case in which it is defined. The patch is started once, before any action
cases run, and stopped once, after all action cases run.

(from: ``pysoa.test.plan.grammar.directives.mock``)

Syntax::

    'mock' ':' mock_target ':' mock_path ':' [exception | delete] value


Mock Result For Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this to patch a target with ``unittest.Mock`` and set up a return value or side effect for that mock or any of
its attributes at any path level. This directive applies to the specific action case in which it is defined. The
patch is started once, after any test-case-level patches (if applicable) are started and before before the action
is called, and stopped once, after the action returns and before any test-case-level patches (if applicable) are
stopped.

For full documentation on how to use this directive, see the documentation for the test-case-level ``mock``
directive, with these revised examples::

    user_action: mock: example_service.actions.users.random: randint.return_value: 31
    user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "abc123"
    user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "def456"
    user_action: mock: example_service.actions.users.uuid: uuid4.side_effect: "ghi789"
    user_action: mock: example_service.actions.users.third_party_object: return_value: {"id": 3, "name": "Hello, world"}
    user_action: mock: example_service.actions.users.third_party_object: foo_attribute.return_value.bar_attribute.side_effect: exception IOError
    user_action: mock: example_service.actions.users.third_party_object: foo_attribute.return_value.qux_attribute: delete

(from: ``pysoa.test.plan.grammar.directives.mock``)

Syntax::

    action ['.' action_index] ':' ['global'] 'mock' ':' mock_target ':' mock_path ':' [exception | delete] value


Stub Action Body For Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set what that stubbed
service action should return in the response body. This is mutually exclusive with stubbing an error to be
returned by the stubbed service action. This follows the standard path-placing syntax used for action request
and expectation directives. This directive applies to an entire test case. The action is stubbed before the first
action case is run, and the stub is stopped after the last action case completes. The following use of this
directive::

    stub action: user: get_user: body int: id: 12
    stub action: user: get_user: body: first_name: John
    stub action: user: get_user: body: last_name: Smith

Is equivalent to this Python code:

.. code-block:: python

    with stub_action('user', 'get_user', body={'id': 12, 'first_name': 'John', 'last_name': 'Smith'}):
        # run all actions in this test

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    'stub action' ':' stub_service ':' stub_action ':' 'body' [data_type] ':' variable_name ':' value


Stub Action Body For Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set what that stubbed
service action should return in the response body. This is mutually exclusive with stubbing an error to be
returned by the stubbed service action. This follows the standard path-placing syntax used for action request
and expectation directives. This directive applies to an individual action case. The action is stubbed immediately
before the action case is run, and the stub is stopped immediately after the action case completes. The
following use of this directive::

    create_bookmark: stub action: user: get_user: body int: id: 12
    create_bookmark: stub action: user: get_user: body: first_name: John
    create_bookmark: stub action: user: get_user: body: last_name: Smith

Is equivalent to this Python code:

.. code-block:: python

    with stub_action('user', 'get_user', body={'id': 12, 'first_name': 'John', 'last_name': 'Smith'}):
        # run the first (possibly only) create_bookmark action case

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':' stub_action ':' 'body' [data_type] ':'
        variable_name ':' value


Stub Action Error For Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set an error that the
stubbed service action should return. This is mutually exclusive with stubbing a response body to be returned by
the stubbed service action. This follows the standard (full) error code/field/message syntax of the error
expectations directives, and the error field may be "none" to indicate that this error should have no field name.
This directive applies to an entire test case. The action is stubbed before the first action case is run, and the
stub is stopped after the last action case completes. The following use of this directive::

    stub action: user: get_user: error: code=NOT_FOUND, field=none, message=The user was not found
    stub action: user: create_user: error: code=INVALID, field=first_name, message=The first name is invalid

Is equivalent to this Python code:

.. code-block:: python

    with stub_action('user', 'get_user', errors=[Error(code='NOT_FOUND', message='The user was not found']), \
            stub_action(
                'user',
                'create_user',
                errors=[Error(code='INVALID', field='first_name', message='The first name is invalid')],
            ):
        # run all actions in this test

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    'stub action' ':' stub_service ':' stub_action ':' 'error' ':' 'code' '=' error_code ',' 'field' '=' field_name ','
        'message' '=' error_message


Stub Action Error For Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set an error that the
stubbed service action should return. This is mutually exclusive with stubbing a response body to be returned by
the stubbed service action. This follows the standard (full) error code/field/message syntax of the error
expectations directives, and the error field may be "none" to indicate that this error should have no field name.
This directive applies to an individual action case. The action is stubbed immediately before the action case is
run, and the stub is stopped immediately after the action case completes. The following use of this directive::

    stub action: user: get_user: error: code=NOT_FOUND, field=none, message=The user was not found
    stub action: user: create_user: error: code=INVALID, field=first_name, message=The first name is invalid

Is equivalent to this Python code:

.. code-block:: python

    with stub_action('user', 'get_user', errors=[Error(code='NOT_FOUND', message='The user was not found']), \
            stub_action(
                'user',
                'create_user',
                errors=[Error(code='INVALID', field='first_name', message='The first name is invalid')],
            ):
        # run all actions in this test

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':' stub_action ':' 'error' ':' 'code' '='
        error_code ',' 'field' '=' field_name ',' 'message' '=' error_message


Stub Action Called For Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set an expectation that
the stubbed action will be called (or not) by the test. If you use this directive without a corresponding
``stub action ... body`` or ``stub action ... error`` directive, the stubbed action will return an empty dict as the
response body. You cannot combine ``expect called`` and ``expect not called`` for the same stubbed action; the two are
mutually exclusive. If you do not specify a variable name and value, the expectation will be that the action is
called with an empty request dict. This directive applies to an entire test case. The action is stubbed before the
first action case is run, and the stub is stopped after the last action case completes.

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    'stub action' ':' stub_service ':' stub_action ':' 'expect' ['not'] 'called' ((':') | ([data_type] ':'
        variable_name ':' value))


Stub Action Called For Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use this directive to stub an action call to another service that your service calls and set an expectation that
the stubbed action will be called (or not) by the test. If you use this directive without a corresponding
``stub action ... body`` or ``stub action ... error`` directive, the stubbed action will return an empty dict as the
response body. You cannot combine ``expect called`` and ``expect not called`` for the same stubbed action; the two are
mutually exclusive. If you do not specify a variable name and value, the expectation will be that the action is
called with an empty request dict. This directive applies to an individual action case. The action is stubbed
immediately before the action case is run, and the stub is stopped immediately after the action case completes.

(from: ``pysoa.test.plan.grammar.directives.stub_action``)

Syntax::

    action ['.' action_index] ':' ['global'] 'stub action' ':' stub_service ':' stub_action ':' 'expect' ['not']
        'called' ((':') | ([data_type] ':' variable_name ':' value))


Freeze Time Test Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~

Freeze Time using freezegun for the duration of an entire test plan.

This will span all actions within the plan, no matter where the statement is located.

(from: ``pysoa.test.plan.grammar.directives.time``)

Syntax::

    'freeze time' ':' value


Freeze Time Action Directive
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Freeze Time using freezegun for the duration of a single action.

(from: ``pysoa.test.plan.grammar.directives.time``)

Syntax::

    action ['.' action_index] ':' ['global'] 'freeze time' ':' value


Extending Test Plans
********************

You can extend test plan syntax to create your own directives, allowing you to add even more features to your test
plans. The base for all directive behavior is contained in the class ``pysoa.test.plan.grammar.directive:Directive``.
Your directives must extend that class directly or indirectly. Extending the base class directly gives you the ability
to manipulate test case-level and global test case-level behavior. In most cases, you'll want to extend
``pysoa.test.plan.grammar.directive:ActionDirective``, which is the base class for all action case behavior. For more
information about how to use and extend these classes, read their extensive docstrings.

Once you have created one or more new directives, you can register them with the PySOA Test Plan system using one of
the following techniques:

- Call ``pysoa.test.plan.grammar.directive:register_directive`` to register your directive with the test plan system
  manually. However, this requires your code that calls that function to be loaded before the PyTest process starts,
  which can be tricky to achieve.
- Use the Python entry point named ``pysoa.test.plan.grammar.directives`` in your ``setup.py`` file. This is a more
  reliable approach that works in all scenarios. Example:

  .. code-block:: python

      from setuptools import setup

      ...

      setup(
          name='base_service',
          description='A layer on top of PySOA that serves as the base for all of our micro services',
          ...
          entry_points={
              'pysoa.test.plan.grammar.directives': [
                  'auth_token_directive = base_service.test.directives:AuthTokenDirective',
                  'authentication_directive = base_service.test.directives:AuthProcessingDirective',
              ],
          },
          ...
      )

.. END AUTO-GENERATED TEST PLAN DOCUMENTATION
