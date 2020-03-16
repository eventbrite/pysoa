Testing with PySOA
==================

PySOA comes with several facilities for testing—both for testing services themselves and for testing code that interacts
with PySOA services. This document describes these libraries and techniques. As always, all strings in the examples
are unicode strings (the default in Python 3; use ``from __future__ import unicode_literals`` for Python 2).

.. contents:: Contents
   :local:
   :depth: 3
   :backlinks: none


Using ``PyTestServerTestCase`` and ``UnitTestServerTestCase``
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

:class:`pysoa.test.server.PyTestServerTestCase` and :class:`pysoa.test.server.UnitTestServerTestCase` are test class
helpers that provide built-in tools for easily testing PySOA service calls. ``PyTestServerTestCase`` is optimized for
PyTest-style tests and supports all the normal PyTest features—fixtures, parametrization, and more.
``UnitTestServerTestCase`` is geared for the fans of ``unittest``-style tests who wish to use the features offered by
``unittest``. It's important to note that many PyTest features (fixtures, parametrization) do not work with test
classes that extend ``UnitTestServerTestCase``. Finally, there is a ``ServerTestCase`` alias of ``PyTestServerTestCase``
if you prefer to use that for brevity.

When writing a PySOA service, there are likely many things for which you will want to write automated tests. If you are
strict about unit tests, you may simply instantiate your action classes and test the individual methods as pure units
of code. If you are less strict about this, or if you want to write integration tests for your service, these two
helper classes make it easy to locally configure your service and make service calls to it with minimal effort.

The examples in this documentation demonstrate using ``PyTestServerTestCase``. The use of ``UnitTestServerTestCase`` is
nearly identical, and you can learn more about it in the linked reference documentation above.


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
of these, every test in the test case will fail in ``setup_method``. Whatever your settings source, the transport will
be overridden by the local transport for the purposes of the tests.

If you override ``setup_method`` in your test case class, be sure to call ``super().setup_method()``; otherwise, your
test class will not set up properly.


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

            assert len(errors) == 1
            assert errors[0].code == FIELD_MISSING
            assert errors[0].field == 'object_id'

        def test_two(self):
            self.assertActionRunsWithFieldErrors('get_object', {}, {'object_id': FIELD_MISSING})

        def test_three(self):
            self.assertActionRunsWithOnlyFieldErrors(
                'get_objects',
                {'object_id': '1234'},
                {'object_id': 'UNEXPECTED_FIELD', 'object_ids': {FIELD_MISSING}},
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
exert more control over how the stub behaves.

While it's possible to use ``body`` or ``errors`` in conjunction with ``side_effect``, it is not recommended unless you
really know what you're doing. It can be confusing for future developers working in your code. See the Python
``unittest.Mock`` documentation for a detailed description of the expected behavior when specifying ``return_value`` and
``side_effect`` at the same time. ``side_effect`` can be a single value of any of the following or a list/tuple (for
multiple calls) where each value is any of the following:

- A response body dict (same as the ``body`` argument to ``stub_action``)
- An instance of ``ActionError`` with one or more SOA errors configured
- A callable, which should accept one argument (which will be the request body dict) and should either return a
  response body dict or raise an ``ActionError``.

``side_effect`` argument is useful for raising exceptions or dynamically changing return values. The function is called
with the same arguments as the mock, and unless it returns DEFAULT, the return value of this function is used as the
return value. Alternatively ``side_effect`` can be an exception class or instance. In this case the exception will be
raised when the mock is called. If ``side_effect`` is an iterable then each call to the mock will return the next value
from the iterable.


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


PySOA Test Plans
++++++++++++++++

.. automodule:: pysoa.test.plan

.. automodule:: pysoa.test.plan.grammar.directive
