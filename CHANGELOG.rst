Changelog
=========

1.4.4 (2022-08-29)
------------------
- Make PySOA compatible with newer versions of attrs (#272)

1.4.3 (2022-08-28)
------------------
- Use Ubuntu 20.04 in Dockerfile

1.4.2 (2021-09-15)
------------------
- Fix mypy annotations
- Disable mypy errors
- Fix Six issues
- Fix unit tests
- Removed Python 3.8 testing from Travis 

1.4.1 (2020-08-05)
------------------
- Fix another mypy annotation.
- Fix mypy annotation.
- Switch argument order.
- Make instance_index optional.
- Disable mypy warning.
- Add missing parameter.
- [MINOR] Pass instance index into transport.

1.4.0 (2020-07-23)
------------------
- [MINOR] Treat UTC datetime strings as datetimes in test plans (#262)
- Capture stubs to autogenerate schemas for contract testing (#261)

1.3.1 (2020-06-24)
------------------
- [PATCH] Prevent creation of empty sequences when global structures are parsed

1.3.0 (2020-06-12)
------------------
- [MINOR] Allow Server subclasses to set a custom introspection action (#257)

1.2.1 (2020-06-12)
------------------
- [PATCH] Fix handling of empty structures in `get_all_paths`
- [PATCH] Update README to install latest version

1.2.0 (2020-04-24)
------------------
- Fix lint error and pytest-asyncio version.
- Move Redis server transport setting to a separate object.
- [PATCH] Fix #251: Replace use of Django's close_old_connections
- [MINOR] Ensure support for Redis 6 with ACLs and TLS

1.1.3 (2020-02-25)
------------------
- [PATCH] Try to make Travis builds faster
- [PATCH] Update documentation
- [PATCH] Fix two bugs regarding client expansions

1.0.4 (2020-02-25)
------------------
- [PATCH] Fix two bugs regarding client expansions
- [PATCH] Update documentation
- [PATCH] Fix #240 - Do not strip whitespace from serialized messages
- [PATCH] Improve error messages and use correct msgpack dependency
- [PATCH] Try to make Travis builds faster
- [PATCH] Fix #239: stub_action side_effect now supports mix of types

1.1.2 (2020-02-04)
------------------
- [PATCH] Fix #240 - Do not strip whitespace from serialized messages

1.1.1 (2020-02-04)
------------------
- [PATCH] Improve error messages and use correct msgpack dependency
- [PATCH] Fix #239: stub_action side_effect now supports mix of types

1.1.0 (2020-01-27)
------------------
- [PATCH] Explicitly test for `-m` invocation in all Python versions
- [MINOR] Add ability to extend context in request.call_local_action

1.0.3 (2020-01-08)
------------------
- [PATCH] Skip Django database connection cleanup in PyTest fixtures

1.0.2 (2020-01-03)
------------------
- [PATCH] Skip Django database connection cleanup in unit tests
- [PATCH] Try importing from typing before typing_extensions
- [PATCH] Add some more tests to verify stub_action functionality

1.0.1 (2019-12-05)
------------------
- [PATCH] Account for potential missing PytestCollectionWarning

1.0.0 (2019-12-02)
------------------
- [MAJOR] Removed deprecated class ``RedisClientSettings``; use ``ClientSettings``, instead.
- [MAJOR] Removed deprecated class ``LocalClientSettings``; use ``ClientSettings``, instead.
- [MAJOR] Removed deprecated class ``PolymorphicClientSettings``; use ``ClientSettings``, instead.
- [MAJOR] Removed deprecated class ``RedisServerSettings``; use ``ServerSettings``, instead.
- [MAJOR] Removed deprecated class ``LocalServerSettings``; use ``ServerSettings``, instead.
- [MAJOR] Removed deprecated class ``PolymorphicServerSettings``; use ``ServerSettings``, instead.
- [MAJOR] Removed deprecated class ``Settings``; use `Conformity Settings <https://conformity.readthedocs.io/en/stable/settings.html>`_, instead.
- [MAJOR] Removed deprecated module ``pysoa.common.metrics``; use `PyMetrics <https://pymetrics.readthedocs.io/en/stable/>`_, instead.
- [MAJOR] Removed deprecated module ``pysoa.common.serializer.exceptions``; use ``pysoa.common.serializer.errors``, instead.
- [MAJOR] Removed deprecated module ``pysoa.common.transport.exceptions``, use ``pysoa.common.transport.errors``, instead.
- [MAJOR] Removed deprecated ``is_caller_error`` argument to and attribute of the ``ActionError`` and ``JobError`` classes; use argument ``set_is_caller_error_to``, instead (and it is now a private attribute). This was removed to eliminate confusion with the ``is_caller_error`` attribute of the ``Error`` class, which has not changed and will not change.
- [MAJOR] Removed deprecated function ``log_level_schema``; use the `Conformity logging helpers <https://conformity.readthedocs.io/en/stable/fields.html#logging-helpers>`_, instead.
- [MAJOR] Removed deprecated client setting ``transport_cache_time_in_seconds``, which has no replacement because transports work differently now than they did when that setting was originally created.
- [MINOR] Add a new server-side ``EnrichedJobRequest`` class to correspond to the server-side ``EnrichedActionRequest``.
- [MAJOR] Refactor the ``ServerMiddleware.job`` interface to accept the ``EnrichedJobRequest`` class instead of a dictionary.
- [MAJOR] Refactor the way middleware and middleware wrapper stacks are constructed to improve performance.
- [MINOR] Improve logging filter to add action name to record
- [MINOR] New class ``BaseServerTestCase`` contains helper methods for setting up the test service, calling actions on the service, and asserting actions runs with and without errors, all of which previously resided directly in ``ServerTestCase``.
- [MINOR] New class ``UnitTestServerTestCase`` extends both ``unittest.TestCase`` and ``BaseServerTestCase`` for when you really want to use ``unittest``-style tests. Its ``setUp`` method calls the helper method for setting up the test service.
- [MINOR] New class ``PyTestServerTestCase`` extends ``BaseServerTestCase``. Its ``setup_class`` method will issue a warning and call ``setUpClass`` if your class has that method. Its ``teardown_class`` method will issue a warning and call ``tearDownClass`` if your class has that method. Its ``setup_method`` method calls the helper method for setting up the test service and will issue a warning and call ``setUp`` if your class has that method. Its ``teardown_method`` method will issue a warning and call ``tearDown`` if your class has that method. If you currently use ``addCleanup``, it will still work but will issue a warning. All the standard ``self.assert*`` and ``self.fail*`` methods are polyfilled and should work similar to the way they previously worked, but you should endeavor to swich over to simple uses of the ``assert`` keyword, which provides better diffs in PyTest failure messages.
- [MAJOR] ``ServerTestCase`` is now an alias for ``PyTestServerTestCase`` instead of a class. If you have existing test classes that extend ``ServerTestCase``, and those tests classes do not start with the word ``Test``, **PyTest will not run them anymore**! You need to rename them to start with ``Test``.
- [MAJOR] The test plan class ``ServicePlanTestCase`` now inherits from ``PyTestServerTestCase`` instead of ``UnitTestServerTestCase`` like it previously did. Test plans behave slightly differently now. Your fixture files should all work the same way they always have, but if you have any advanced uses of setup or teardown methods, they may break.
- [PATCH] Fixes a bug in ``stub_action`` preventing it from working as a decorator in PyTest-style unit test methods (it already worked properly in ``unittest``-style unit test methods).
- [MAJOR] Bump PyMetrics to 1.0.x
- [MAJOR] Make Version 3 the default Redis gateway protocol version
- [PATCH] Add documentation about release roadmap

1.0.0-rc1 (2019-11-25)
----------------------
- [MAJOR] Make Version 3 the default Redis gateway protocol version

1.0.0-beta2 (2019-11-23)
------------------------
- [PATCH] Add missing assertLogs, fix assertCountEqual, rename some tests

1.0.0-beta1 (2019-11-22)
------------------------
- [MAJOR] Bump PyMetrics to 1.0.x
- [MAJOR] Refactor ServerTestCase to not inherit from unittest.TestCase
- [PATCH] Fix new typing issues in MyPy 0.740
- [MINOR] Improve logging filter to add action name to record
- [MAJOR] Implement #197: Refactor ServerMiddleware job with EnrichedJobRequest
- [MAJOR] #196: Remove all deprecated features before release 1.0.0

0.74.0 (2019-11-05)
-------------------
- [MINOR] Publish documentation on ReadTheDocs.io

0.73.0 (2019-11-01)
-------------------
- [PATCH] Add support for Python 3.8
- [MINOR] Add gauges to track running and busy PySOA workers
- [MINOR] Improve `Server.make_client`, including with adding `calling_service`

0.72.0 (2019-10-30)
-------------------
- [PATCH] Expand functional test system with more Redis

0.71.1 (2019-10-09)
-------------------
- [PATCH] Fix typing for stub_action's side_effect

0.71.0 (2019-10-09)
-------------------
- [PATCH] Fix incorrect type annotation on Error.variables
- [MINOR] Refactor PySOA errors for easier and more concise usage
- [MAJOR] Adopt PyMetrics and remove metrics shims
- [PATCH] Remove noqa comments now that Flake8 3.7.8 is out

0.70.1 (2019-09-26)
-------------------
- [PATCH] Fix tests broken by releasing 0.70.0

0.70.0 (2019-09-26)
-------------------
- [MINOR] #204: Add is_caller_error attribute to Error objects

0.69.1 (2019-09-23)
-------------------
- [PATCH] Be permissive about string types in assertions

0.69.0 (2019-09-23)
-------------------
- [MAJOR] Add Python typing comments to type the API

0.68.0 (2019-09-19)
-------------------
- [PATCH] Make typing dependency more specific to fix missing types
- [MINOR] Use Conformity's Settings and deprecate PySOA's Settings

0.67.1 (2019-09-13)
-------------------
- [PATCH] Fix import errors in Python 3.5.2/3.6.1 and fix Harakiri logging

0.67.0 (2019-09-12)
-------------------
- [MINOR] Fix #198: Double import trap is broken in Python 3.7
- [PATCH] Update docs further
- [MAJOR] Add support for response chunking to Redis Gateway transport
- [MAJOR] Support UTC-aware datetime objects in MsgpackSerializer

0.66.0 (2019-08-23)
-------------------
- [MINOR] Add pre-fork hook method to Server class, clean up prints
- [MINOR] Further improve harakiri and verify with functional tests
- [PATCH] Update test documentation to use FIELD_MISSING constant instead of string (#184)

0.65.0 (2019-08-20)
-------------------
- [MINOR] Refactor harakiri to log details about running threads' stacks
- [MINOR] Add robust support for safe asynchronous code
- [PATCH] Clean up Travis file using config.travis-ci.org

0.64.1 (2019-07-18)
-------------------
- [PATCH] Commit metrics during perform_pre_request_actions

0.64.0 (2019-07-18)
-------------------
- [MINOR] Respawn crashed workers when running in forking mode

  - By default, when running in forking mode, PySOA will respawn crashed workers.
  - If a worker crashes 3 times in 15 seconds or 8 times in 60 seconds, PySOA will give up and stop respawning that worker.
  - The new `--no-respawn` argument can disable this behavior if necessary.
  - If all workers crash too many times and PySOA runs out of workers, it exits (this is basically the existing behavior, except for the above-described respawning).

- [MINOR] Add first functional tests and fix some bugs

  - Create a functional test environment using Docker/Docker Compose and a simple shell script.
  - Add an initial set of functional tests.
  - Fix several bugs regarding signal handling in the `Server`, server process forking, and file-watching auto-reloader:

    - If the server received several simultaneous signals (for example, if Ctrl+C is used), the signal handler could be invoked in parallel two or more times, resulting in, at best, forcefully-terminating the server and, at worst, that plus a bunch of concurrency errors. This is now fixed.
    - If server process forking was enabled or the file-watching auto-reloader was enabled, non-Ctrl+C signals (such as those from Docker when running within a container) were suppressed, meaning the server would not stop.

- [PATCH] Re-organize all tests into `unit`, `integration`, and `functional` test modules

0.63.0 (2019-07-05)
-------------------
- [MINOR] Support PyTest 5.0 with tests ensuring compliance

0.62.1 (2019-06-28)
-------------------
- [PATCH] Fix misleading DeprecationWarning

0.62.0 (2019-06-24)
-------------------
- [MINOR] Switch to using Conformity's class schemas (all existing configurations are backwards compatible and will continue to work).
- [MINOR] Deprecated `pysoa.server.settings.PolymorphicServerSettings` and `pysoa.client.settings.PolymorphicClientSettings`. The base `ServerSettings` and `ClientSettings` are now automatically polymorphic and you should use / inherit from those, instead.
- [MINOR] Changed the default settings class in `Client.settings_class` from `PolymorphicClientSettings` to `ClientSettings`.
- [MINOR] Changed the default settings class in `Server.settings_class` from `PolymorphicServerSettings` to `ServerSettings`.
- [MAJOR] Refactored the schemas in `LocalClientTransportSchema`, `LocalServerTransportSchema`, `RedisTransportSchema`, `StubClientTransportSchema, and `MetricsSchema` to support the new Conformity class schemas. This breaking change is only a disruption if you are using these classes directly. However, this is unusual and you are probably not. This does not break configurations that were processed by these schemas.
- [MAJOR] Deleted module `pysoa.common.schemas` and its classes `BasicClassSchema` and `PolymorphClassSchema`. This breaking change is only a disruption if you are using these classes directly. However, this is unusual and you are probably not.
- [MINOR] Previously, when a `Settings` object failed to validate against the settings schema, it might have raised `ValueError`, Conformity's `ValidationError`, _or_ `Settings.ImproperlyConfigured`. Now it will _always_ raise _only_ `Settings.ImproperlyConfigured` when it fails to validate against the settings schema.

0.61.2 (2019-06-21)
-------------------
- [PATCH] Fix several tests broken by Conformity 1.25.0

0.61.1 (2019-06-21)
-------------------
- [PATCH] Return same stub in multiple uses of the same stub_action instance
- [PATCH] Allow multiple uses of the same stub_action instance

0.61.0 (2019-05-29)
-------------------
- [MAJOR] Remove PySOA server import from pysoa/server/__init__.py

0.60.0 (2019-05-24)
-------------------
- [MINOR] Add forked process ID for creating deterministic heartbeat files
- [MINOR] Add helper for calling local actions within other actions

0.59.2 (2019-05-10)
-------------------
- [PATCH] Guarantee Server always has _async_event_loop_thread attribute

0.59.1 (2019-04-23)
-------------------
- [PATCH] #161: Fix server to start async event loop thread, thread to join properly

0.59.0 (2019-04-18)
-------------------
- [MINOR] Bump Conformity to 1.21
- [PATCH] Update iSort settings and re-apply iSort
- [PATCH] Use Tox to add tests for PyInotify

0.58.2 (2019-05-10)
-------------------
- [PATCH] Guarantee Server always has _async_event_loop_thread attribute

0.58.1 (2019-04-23)
-------------------
- [PATCH] #161: Fix server to start async event loop thread, thread to join properly

0.58.0 (2019-04-11)
-------------------
- [PATCH] Fix issues #152 and #156 resulting in IndexErrors
- [MINOR] Bump Conformity, Attrs to support Attrs 17.4 - 19.x
- [PATCH] Fix exceptions being thrown for missing job request keys (#154)
- [MAJOR] Step 2 in the message serializer content type header
- [PATCH] Run the event loop in a separate thread. (#150)
- [PATCH] Fix tests broken by latest PyTest version

0.57.0 (2019-01-31)
-------------------
- [PATCH] Use client timeout for expansions receive responses
- [PATCH] Fix test failures introduced by PyTest 4.2.0
- [MINOR] Fix build failures and preempt Travis deploy failure

0.56.0 (2018-12-05)
-------------------
- [PATCH] Update test compatibility tools to eliminate warnings
- [MINOR] Allow use of `raise_job_errors` and `catch_transport_errors`

0.55.2 (2018-11-19)
-------------------
- [PATCH] Throttle updates of the heartbeat file

0.55.1 (2018-11-15)
-------------------
- [PATCH] Support newer versions of several dependencies

0.55.0 (2018-11-12)
-------------------
- [MINOR] Prevent server shutdown on request with non-unicode context keys (#143)
- [MAJOR] Add support for switching message serializer with content type header

0.54.2 (2018-10-24)
-------------------
- [PATCH] Fix new flake8 errors

0.54.1 (2018-10-22)
-------------------
- [PATCH] Add MTU cache to SyslogHandler to improve performance

0.54.0 (2018-10-16)
-------------------
- [MINOR] A better Syslog logging handler
- [MINOR] Allow setting `side_effect` while defining the stub
- [MINOR] Simplify `stub_action` decorator implementation

0.53.0 (2018-10-05)
-------------------
- [MINOR] If timeout specified, include it in the control header

0.52.0 (2018-10-01)
-------------------
- [MINOR] Remove deprecated use of "encoding" argument in msgpack.unpackb
- [PATCH] Remove use of deprecated assertEquals
- [PATCH] Remove use of deprecated EntryPoint.load
- [PATCH] Fix usage of deprecated attr.it `convert` parameter

0.51.1 (2018-09-07)
-------------------
- [PATCH] Move extra_fields_to_redact from common to server settings

0.51.0 (2018-09-06)
-------------------
- [MINOR] Allow extra keys to be redacted/censored from logs via settings (#128)
- [MAJOR] Fix bug allowing missing `kwargs` in Redis, Local, and Stub transports

0.50.0 (2018-09-04)
-------------------
- [MINOR] Make the polymorphic client and server settings extensible

0.49.0 (2018-09-04)
-------------------
- [PATCH] Extract server settings to a separate fixture
- [MINOR] Add support for a heartbeat file
- [MINOR] Add managed event loop to all action requests for convenience in Python 3 services

0.48.0 (2018-08-23)
-------------------
- [MINOR] Add tools to support pytesty testing in pysoa services (#122)

0.47.0 (2018-08-15)
-------------------
- [MINOR] Improve logging configuration to not conflict with Django

0.46.0 (2018-08-10)
-------------------
- [MINOR] Fix the resolution of the server idle time metric
- [MINOR] Add support for managing the lifecycle of Django cache engines and connections
- Fix python3.7 build (as well as staging) on Travis CI (#116)

0.45.0 (2018-08-06)
-------------------
- [MAJOR] Add support for non-blocking client futures
- [MINOR] Apply isort and clean up imports
- [MINOR] Remove unused meta header for retired double-serialization
- [PATCH] Add documentation for the platform-independent PySOA protocol

0.44.1 (2018-07-17)
-------------------
- [PATCH] Fix big introduced by logging rename

0.44.0 (2018-07-16)
-------------------
- [MINOR] adding support for errors due insufficient permissions (#108)
- [MINOR] Add option to suppress responses for send-and-forget
- [MAJOR] Make the maximum Redis transport message size configurable
- [MAJOR] Add a response context dict to all responses

0.43.0 (2018-06-29)
-------------------
- [MINOR] Fix database error sometimes encountered during idle cleanup

0.42.0 (2018-06-25)
-------------------
- [MINOR] Add directives for using stub_action from test plans
- [MAJOR] Fix bug causing server to shut down on unserializable responses
- [MINOR] Add directives for using Mock from test plans

0.41.0 (2018-06-04)
-------------------
- [MINOR] Add static Server initializer to support settings and server patching
- [MINOR] Add support for decimal.Decimal in MessagePack serializer

0.40.0 (2018-05-12)
-------------------
- [MINOR] Bump Conformity
- [MINOR] Remove the transport cache as it is no longer needed
- [MINOR] Add more documentation
- [MINOR] Add a SwitchedAction class to facilitate switch usage

0.39.0 (2018-05-09)
-------------------
- [MINOR] Add more field names to the set of log redactions

0.38.2 (2018-05-09)
-------------------
- [PATCH] Import Mock if installed before unittest.mock

0.38.1 (2018-05-04)
-------------------
- [PATCH] Fix optionality of test plans

0.38.0 (2018-05-03)
-------------------
- [MINOR] Add idle timer for tracking how long servers stay idle
- [PATCH] Ensure an error response is sent if response too large
- [MINOR] Don't require mock library for `stub_service`, tests in Python 3
- [MINOR] Use error codes supplied by Conformity

0.37.1 (2018-04-27)
-------------------
- Properly copy PyTest marks to fixture test cases
- Improve auto-docs using built-in method designed for it

0.37.0 (2018-04-25)
-------------------
- [MAJOR] Add extensive test plan system with customized test plan syntax

0.36.1 (2018-04-14)
-------------------
- [PATCH] Add client receive timeout metric

0.36.0 (2018-04-13)
-------------------
- [MINOR] Better handling of out-of-order responses
- [MAJOR] Fix several expansion bugs and refactor configuration
- [MINOR] Ensure stub_action supports expansions
- [PATCH] Add pip cache to Travis
- [MAJOR] Support sending multiple requests to execute in parallel

0.35.0 (2018-04-05)
-------------------
- [MINOR] Add stock ability to include other services' status in status
- [MAJOR] Add support for setting a custom timeout when sending a request

0.34.0 (2018-03-27)
-------------------
- Improve logging defaults and support for Syslog

0.33.1 (2018-03-19)
-------------------
- Corrected binary distribution wheel

0.33.0 (2018-03-19)
-------------------
- [MINOR] Censor sensitive fields in the request and response log

0.32.1 (2018-03-13)
-------------------
- Re-raise InvalidExpansionKey for expansion exception when request has invalid key

0.32.0 (2018-03-01)
-------------------
NOTE: This release contains a breaking change, not for existing services/code, but for existing metrics graphs and reports utilizing any of the timer metrics PySOA records. Previously, the value these graphs and reports displayed represented a number with millisecond units. Now, they will be a number with microsecond units. As such, without the context of this change in mind, performance will appear to get worse by three orders of magnitude across the board on all existing graphs after a release deployment.
- [MAJOR] Switch to microsecond resolution for metrics timers
- [MINOR] Add support for metric timer resolution

0.31.0 (2018-02-27)
-------------------
- Ensure actionless job request causes validation error
- Ensure that action errors also trigger higher level logging
- Fix expansion response format

0.30.5 (2018-02-22)
-------------------
- Make disable_existing_loggers default to False to allow module-level getLogger

0.30.4 (2018-02-21)
-------------------
- Ensure logging context works with local services by using a stack

0.30.3 (2018-02-21)
-------------------
- [PATCH] Fix improper type for logging logger propagate setting
- [PATCH] Refactor test_expansion: renaming with well-known book-author to present intuitive relations, instead of foo/bar/baz

0.30.2 (2018-02-16)
-------------------
- [PATCH] If no databases are configured, do not attempt Django connection cleanup

0.30.1 (2018-02-15)
-------------------
- Relax version spec for Six to reduce version conflicts

0.30.0 (2018-02-15)
-------------------
- Rename test module packages that were redundantly named
- Add support for server introspection
- Add request details to a logging context for all log records

0.29.0 (2018-02-14)
-------------------
- Bump Conformity
- Add support for controlling request log logging level
- Add support for clean-up operations before and after requests

0.28.1 (2018-02-07)
-------------------
- Just a little defensive programming so that we don't break status actions

0.28.0 (2018-02-07)
-------------------
- Refactor expansion methods 
- Renaming to differentiate expansion_config init v.s. expansions from request 
- When make request, the `body` takes `[value]` instead of `value`, assuming we always call batch endpoints 
- When expand, the initial `exp_service_requests` set to empty, because the upstream `service` has been called before this method.

0.27.0 (2018-02-06)
-------------------
- Bump Conformity and remove duplicate msgpack-python dependency
- Add support for auto-reloading code changes in dev environments
- Use Invoke Release for releases going forward
- Fix bug causing response mix-ups with transport cache
- Add ability to fork multiple server processes with the standalone command
- Start request counter at a random value (#50)
- Add .pytest_cache to .gitignore
- Remove mock of randint
- Improve status action to enable abbreviated responses when only the version is needed
- Tweak comment

0.26.1 (2018-01-20)
-------------------
- Ensure double-import trap doesn't catch entrypoint execution

0.26.0 (2018-01-19)
-------------------
- Remove duplicate serialization from the server now that clients are no longer requesting serialization
- Bump Attrs, Conformity, and PyTest
- Add standalone helpers to eliminate lots of boilerplace code across services
- Fix a documentation typo

0.25.0 (2018-01-12)
-------------------
- Attempt two at removing duplicate serialization from the client now that ASGI (incompatible) is removed

0.24.0 (2018-01-11)
-------------------
- BREAKING CHANGE: Remove the deprecated and unused ASGI Transport
- BREAKING CHANGE: Ensure that the service name passed to the client is always unicode

0.23.1 (2018-01-09)
-------------------
- Recognize either settings variable name in non-Django services

0.23.0 (2018-01-08)
-------------------
- Improve the msgpack serializer to support local-date and dateless-time objects
- Add extensive testing documentation and fix bug in ServerTestCase
- Add base status action class for creating easy healthcheck actions
- Ensure metrics are published after server startup
- Fix stub_action bug that made ActionErrors not work as side effects
- Improve transport error messages with service name

0.22.1 (2017-12-21)
-------------------
- Add stub_action helper for use as decorator or context manager in tests

0.22.0 (2017-12-19)
-------------------
- Use `master_for` correctly to reduce number of Redis connections

0.21.2 (2017-12-18)
-------------------
- Fix issue causing client metrics to not record when transport cache enabled

0.21.1 (2017-12-08)
-------------------
- Roll back the phase-out of double-serialization due to incompatibility with ASGI-Redis

0.21.0 (2017-12-04)
-------------------
- Add option for PySOA server to gracefully recover from Redis master failover
- Add support for a cached client transport to increase connection re-use
- Improve server startup log to include additional information

0.20.1 (2017-11-28)
-------------------
- Don't record receive metrics timer in server if no message received

0.20.0 (2017-11-14)
-------------------
- Phase out double-serialization in favor of transport-only serialization

0.19.2 (2017-11-13)
-------------------
- Add a few more metrics to help identify potential client-creation bottlenecks

0.19.1 (2017-11-08)
-------------------
- Fix #22: Missing key issue when client and server on different Python versions

0.19.0 (2017-11-07)
-------------------
- Add new direct Redis transport that doesn't use ASGI
- Deprecate ASGI transport due to performance issues
- Add support for recording metrics directly within SOA clients, servers, and transports
- General clean-up and improvements

0.18.1 (2017-10-18)
-------------------
- Add exception info to error logging

0.18.0 (2017-10-13)
-------------------
- Add support for `in` keyword in SOA settings

0.17.3 (2017-09-18)
-------------------
- Use uuid4 instead of uuid1 to calculate the client ID

0.17.2 (2017-09-18)
-------------------
- Pin the versions of six and attrs

0.17.1 (2017-09-14)
-------------------
- LocalTransportSchema server class can be a path or a class object

0.17.0 (2017-09-11)
-------------------
- Ensure that switches from Client.context are correctly merged with the switches passed to each request

0.16.0 (2017-08-17)
-------------------
- Improve schema validation for client transport settings, including settings schema for ASGI, local and multi-backend Clients

0.15.0 (2017-08-11)
-------------------
- Add helpers to ServerTestCase to make calling actions and asserting errors easier

0.14.0 (2017-08-10)
-------------------
- Merge routing functionality into the Client, and remove ClientRouter

0.13.1 (2017-07-21)
-------------------
- Exposed expansions to actions.

0.13.0 (2017-07-19)
-------------------
- Added initial implementation of PySOA expansions to the ClientRouter
- Fixed a small bug in the local transport that broke tests for Python 3.
- Updated the router configuration dictionary format to include type expansions and routes.

0.12.2 (2017-06-16)
-------------------
- Fixed signature of middleware instantiation in ClientRouter._make_client

0.12.1 (2017-06-14)
-------------------
- Added logging for critical server errors

0.12.0 (2017-06-12)
-------------------

- Option to disable harakiri by setting timeout to 0
- Add channel capacities argument to ASGI transport core

0.11.0 (2017-05-19)
-------------------

- Updated the ASGI transport backend to use the new version of asgi_redis
- Improved the local client transport and renamed to LocalClientTransport
- Added settings schema for ASGI transports
- Added settings classes for ASGI-backed Server and Client
- Made MsgpackSerializer the default serializer for all Servers and Clients

0.10.0 (2017-05-09)
-------------------

- Updated the ASGI transport backend to support multiple Redis masters and Sentinel

0.9.0 (2017-05-08)
------------------

- New ServerTestCase for writing tests against Servers and their actions
- Allow variables to be included with errors and then sends the response down with failed serialization

0.8.1 (2017-05-01)
------------------
- Update ThreadlocalClientTransport to support both import paths and objects at initialization
- Make Server class somewhat Django-compatible

0.8.0 (2017-04-26)
------------------
- Client middleware uses onion calling pattern

0.7.0 (2017-04-17)
------------------
- Changed middleware to work in a callable (new-Django) style

0.6.1 (2017-04-17)
------------------
- Fixed an issue wherein the ASGI transport class was violating the ASGI message protocol requirement for unicode message keys when running under Python 2.
- Fixed a bug that caused the Server to crash when instantiating middleware classes from settings.

0.6.0 (2017-04-17)
------------------
- Make SOASettings middleware schema consistent with transport and serializer schema
- Updated PySOA to be Python 3 compatible.

0.5.0 (2017-04-10)
------------------
- Make stub service a real service with a real server and real actions, using ThreadlocalClientTransport
- ActionResponse automatically converts errors to Error type
- Error type accepts both `field` and `traceback` properties, both optional.

0.4.1 (2017-04-07)
------------------
- Updated ASGI client transport to support latest asgiref channel name syntax

0.4.0 (2017-03-31)
------------------
- Use custom attrs types at all edges, for consistency
- Die when killed, Harakiri when locked

0.3.4 (2017-03-30)
------------------
- Refactored Server to have more modular JobRequest processing
- Added Client and Server threadlocal transport classes

0.3.3 (2017-03-28)
------------------
- Make Client.call_actions take extra control arguments
- Settings merge values with defaults

0.3.2 (2017-03-23)
------------------
- Fixed a bug wherein ActionResponse.action was not being set upon initialization.

0.3.1 (2017-03-22)
------------------
- Fix a few incorrect imports

0.3.0 (2017-03-22)
------------------
- ASGI transport
- JSON and MessagePack serializers
- Update the client interface with call_action and call_actions
- Request and response validation

0.2.0 (2017-03-17)
------------------
- Update Client middleware interface.
- Client now keeps track of request IDs and passes them to Transport.send_request_message

0.1.dev2 (2017-03-16)
---------------------
- Updated JobRequest and related schemas
- Added overridable server setup method
- Basic logging support

0.1.dev1 (2017-03-14)
---------------------
- Initial tagged development release
