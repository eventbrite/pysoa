PySOA Reference Documentation
=============================

This file contains the reference documentation for the classes and functions you are likely to consume when using
PySOA. It does not contain the reference documentation for all code in PySOA, which you can view by browsing the
`source code <https://github.com/eventbrite/pysoa/tree/master/pysoa>`_.

**NOTE:** In each place where you see ``union[str, unicode]``, this means that the parameter type should be or the
return type will be a ``str`` (Unicode) in Python 3 and a ``unicode`` in Python 2. You may not use ``str`` in Python
2.

.. contents:: Contents
   :depth: 3
   :backlinks: none


.. _pysoa.client.client.Client:

``class Client``
++++++++++++++++

**module:** ``pysoa.client.client``

- ``object``

  - ``Client``

The ``Client`` provides a simple interface for calling actions on services and supports both sequential and
parallel action invocation.

.. _pysoa.client.client.Client-constructor-docs:

Constructor
***********

Parameters
  - ``config`` (``dict``) - The entire client configuration dict, whose keys are service names and values are settings dicts
    abiding by the ``PolymorphicClientSettings`` schema
  - ``expansion_config`` (``dict``) - The optional expansion configuration dict, if this client supports expansions, which
    is a dict abiding by the ``ExpansionSettings`` schema
  - ``settings_class`` (``union[class, callable]``) - An optional settings schema enforcement class or callable to use, which overrides the
    default of ``PolymorphicClientSettings``
  - ``context`` - An optional base request context that will be used for all requests this client instance sends
    (individual calls can add to and override the values supplied in this context dict)
    :type: dict

.. _pysoa.client.client.Client.call_action:

``method call_action(service_name, action, body=None, **kwargs)``
*****************************************************************

Build and send a single job request with one action.

Returns the action response or raises an exception if the action response is an error (unless
``raise_action_errors`` is passed as ``False``) or if the job response is an error (unless ``raise_job_errors`` is
passed as ``False``).

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service to call
  - ``action`` (``union[str, unicode]``) - The name of the action to call
  - ``body`` (``dict``) - The action request body
  - ``expansions`` (``dict``) - A dictionary representing the expansions to perform
  - ``raise_job_errors`` (``bool``) - Whether to raise a JobError if the job response contains errors (defaults to ``True``)
  - ``raise_action_errors`` (``bool``) - Whether to raise a CallActionError if any action responses contain errors (defaults
    to ``True``)
  - ``timeout`` (``int``) - If provided, this will override the default transport timeout values to; requests will expire
    after this number of seconds plus some buffer defined by the transport, and the client will not
    block waiting for a response for longer than this amount of time.
  - ``switches`` (``list``) - A list of switch value integers
  - ``correlation_id`` (``union[str, unicode]``) - The request correlation ID
  - ``continue_on_error`` (``bool``) - Whether to continue executing further actions once one action has returned errors
  - ``context`` (``dict``) - A dictionary of extra values to include in the context header
  - ``control_extra`` (``dict``) - A dictionary of extra values to include in the control header

Returns
  ``ActionResponse`` - The action response

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``JobError``, ``CallActionError``

.. _pysoa.client.client.Client.call_action_future:

``method call_action_future(service_name, action, body=None, **kwargs)``
************************************************************************

This method is identical in signature and behavior to ``call_action``, except that it sends the request and
then immediately returns a ``FutureResponse`` instead of blocking waiting on a response and returning
an ``ActionResponse``. Just call ``result(timeout=None)`` on the future response to block for an available
response. Some of the possible exceptions may be raised when this method is called; others may be raised when
the future is used.

Parameters
  - ``service_name``
  - ``action``
  - ``body``

Returns
  ``Client.FutureResponse`` - A future from which the action response can later be retrieved

.. _pysoa.client.client.Client.call_actions:

``method call_actions(service_name, actions, expansions=None, raise_job_errors=True, raise_action_errors=True, timeout=None, **kwargs)``
****************************************************************************************************************************************

Build and send a single job request with one or more actions.

Returns a list of action responses, one for each action in the same order as provided, or raises an exception
if any action response is an error (unless ``raise_action_errors`` is passed as ``False``) or if the job response
is an error (unless ``raise_job_errors`` is passed as ``False``).

This method performs expansions if the Client is configured with an expansion converter.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service to call
  - ``actions`` (``iterable[union[ActionRequest, dict]]``) - A list of ``ActionRequest`` objects and/or dicts that can be converted to ``ActionRequest`` objects
  - ``expansions`` (``dict``) - A dictionary representing the expansions to perform
  - ``raise_job_errors`` (``bool``) - Whether to raise a JobError if the job response contains errors (defaults to ``True``)
  - ``raise_action_errors`` (``bool``) - Whether to raise a CallActionError if any action responses contain errors (defaults
    to ``True``)
  - ``timeout`` (``int``) - If provided, this will override the default transport timeout values to; requests will expire
    after this number of seconds plus some buffer defined by the transport, and the client will not
    block waiting for a response for longer than this amount of time.
  - ``switches`` (``list``) - A list of switch value integers
  - ``correlation_id`` (``union[str, unicode]``) - The request correlation ID
  - ``continue_on_error`` (``bool``) - Whether to continue executing further actions once one action has returned errors
  - ``context`` (``dict``) - A dictionary of extra values to include in the context header
  - ``control_extra`` (``dict``) - A dictionary of extra values to include in the control header

Returns
  ``JobResponse`` - The job response

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``JobError``, ``CallActionError``

.. _pysoa.client.client.Client.call_actions_future:

``method call_actions_future(service_name, actions, expansions=None, raise_job_errors=True, raise_action_errors=True, timeout=None, **kwargs)``
***********************************************************************************************************************************************

This method is identical in signature and behavior to ``call_actions``, except that it sends the request and
then immediately returns a ``FutureResponse`` instead of blocking waiting on a response and returning a
``JobResponse``. Just call ``result(timeout=None)`` on the future response to block for an available
response. Some of the possible exceptions may be raised when this method is called; others may be raised when
the future is used.

Parameters
  - ``service_name``
  - ``actions``
  - ``expansions``
  - ``raise_job_errors``
  - ``raise_action_errors``
  - ``timeout``

Returns
  ``Client.FutureResponse`` - A future from which the job response can later be retrieved

.. _pysoa.client.client.Client.call_actions_parallel:

``method call_actions_parallel(service_name, actions, **kwargs)``
*****************************************************************

Build and send multiple job requests to one service, each job with one action, to be executed in parallel, and
return once all responses have been received.

Returns a list of action responses, one for each action in the same order as provided, or raises an exception
if any action response is an error (unless ``raise_action_errors`` is passed as ``False``) or if any job response
is an error (unless ``raise_job_errors`` is passed as ``False``).

This method performs expansions if the Client is configured with an expansion converter.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service to call
  - ``actions`` (``iterable[union[ActionRequest, dict]]``) - A list of ``ActionRequest`` objects and/or dicts that can be converted to ``ActionRequest`` objects
  - ``expansions`` (``dict``) - A dictionary representing the expansions to perform
  - ``raise_action_errors`` (``bool``) - Whether to raise a CallActionError if any action responses contain errors (defaults
    to ``True``)
  - ``timeout`` (``int``) - If provided, this will override the default transport timeout values to; requests will expire
    after this number of seconds plus some buffer defined by the transport, and the client will not
    block waiting for a response for longer than this amount of time.
  - ``switches`` (``list``) - A list of switch value integers
  - ``correlation_id`` (``union[str, unicode]``) - The request correlation ID
  - ``continue_on_error`` (``bool``) - Whether to continue executing further actions once one action has returned errors
  - ``context`` (``dict``) - A dictionary of extra values to include in the context header
  - ``control_extra`` (``dict``) - A dictionary of extra values to include in the control header

Returns
  ``Generator[ActionResponse]`` - A generator of action responses

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``JobError``, ``CallActionError``

.. _pysoa.client.client.Client.call_actions_parallel_future:

``method call_actions_parallel_future(service_name, actions, **kwargs)``
************************************************************************

This method is identical in signature and behavior to ``call_actions_parallel``, except that it sends the requests
and then immediately returns a ``FutureResponse`` instead of blocking waiting on responses and returning a
generator. Just call ``result(timeout=None)`` on the future response to block for an available response (which
will be a generator). Some of the possible exceptions may be raised when this method is called; others may be
raised when the future is used.

If argument ``raise_job_errors`` is supplied and is ``False``, some items in the result list might be lists of job
errors instead of individual ``ActionResponse``s. Be sure to check for that if used in this manner.

If argument ``catch_transport_errors`` is supplied and is ``True``, some items in the result list might be instances
of ``Exception`` instead of individual ``ActionResponse``s. Be sure to check for that if used in this manner.

Parameters
  - ``service_name``
  - ``actions``

Returns
  ``Client.FutureResponse`` - A generator of action responses that blocks waiting on responses once you begin iteration

.. _pysoa.client.client.Client.call_jobs_parallel:

``method call_jobs_parallel(jobs, expansions=None, raise_job_errors=True, raise_action_errors=True, catch_transport_errors=False, timeout=None, **kwargs)``
***********************************************************************************************************************************************************

Build and send multiple job requests to one or more services, each with one or more actions, to be executed in
parallel, and return once all responses have been received.

Returns a list of job responses, one for each job in the same order as provided, or raises an exception if any
job response is an error (unless ``raise_job_errors`` is passed as ``False``) or if any action response is an
error (unless ``raise_action_errors`` is passed as ``False``).

This method performs expansions if the Client is configured with an expansion converter.

Parameters
  - ``jobs`` (``iterable[dict(service_name=union[str, unicode], actions=list[union[ActionRequest, dict]])]``) - A list of job request dicts, each containing ``service_name`` and ``actions``, where ``actions`` is a
    list of ``ActionRequest`` objects and/or dicts that can be converted to ``ActionRequest`` objects
  - ``expansions`` (``dict``) - A dictionary representing the expansions to perform
  - ``raise_job_errors`` (``bool``) - Whether to raise a JobError if any job responses contain errors (defaults to ``True``)
  - ``raise_action_errors`` (``bool``) - Whether to raise a CallActionError if any action responses contain errors (defaults
    to ``True``)
  - ``catch_transport_errors`` (``bool``) - Whether to catch transport errors and return them instead of letting them
    propagate. By default (``False``), the errors ``ConnectionError``,
    ``InvalidMessageError``, ``MessageReceiveError``, ``MessageReceiveTimeout``,
    ``MessageSendError``, ``MessageSendTimeout``, and ``MessageTooLarge``, when raised by
    the transport, cause the entire process to terminate, potentially losing
    responses. If this argument is set to ``True``, those errors are, instead, caught,
    and they are returned in place of their corresponding responses in the returned
    list of job responses.
  - ``timeout`` (``int``) - If provided, this will override the default transport timeout values to; requests will expire
    after this number of seconds plus some buffer defined by the transport, and the client will not
    block waiting for a response for longer than this amount of time.
  - ``switches`` (``list``) - A list of switch value integers
  - ``correlation_id`` (``union[str, unicode]``) - The request correlation ID
  - ``continue_on_error`` (``bool``) - Whether to continue executing further actions once one action has returned errors
  - ``context`` (``dict``) - A dictionary of extra values to include in the context header
  - ``control_extra`` (``dict``) - A dictionary of extra values to include in the control header

Returns
  ``list[union(JobResponse, Exception)]`` - The job response

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``JobError``, ``CallActionError``

.. _pysoa.client.client.Client.call_jobs_parallel_future:

``method call_jobs_parallel_future(jobs, expansions=None, raise_job_errors=True, raise_action_errors=True, catch_transport_errors=False, timeout=None, **kwargs)``
******************************************************************************************************************************************************************

This method is identical in signature and behavior to ``call_jobs_parallel``, except that it sends the requests
and then immediately returns a ``FutureResponse`` instead of blocking waiting on all responses and returning
a ``list`` of ``JobResponses``. Just call ``result(timeout=None)`` on the future response to block for an available
response. Some of the possible exceptions may be raised when this method is called; others may be raised when
the future is used.

Parameters
  - ``jobs``
  - ``expansions``
  - ``raise_job_errors``
  - ``raise_action_errors``
  - ``catch_transport_errors``
  - ``timeout``

Returns
  ``Client.FutureResponse`` - A future from which the list of job responses can later be retrieved

.. _pysoa.client.client.Client.get_all_responses:

``method get_all_responses(service_name, receive_timeout_in_seconds=None)``
***************************************************************************

Receive all available responses from the service as a generator.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service from which to receive responses
  - ``receive_timeout_in_seconds`` (``int``) - How long to block without receiving a message before raising
    ``MessageReceiveTimeout`` (defaults to five seconds unless the settings are
    otherwise).

Returns
  ``generator`` - A generator that yields (request ID, job response)

Raises
  ``ConnectionError``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``StopIteration``

.. _pysoa.client.client.Client.send_request:

``method send_request(service_name, actions, switches=None, correlation_id=None, continue_on_error=False, context=None, control_extra=None, message_expiry_in_seconds=None, suppress_response=False)``
******************************************************************************************************************************************************************************************************

Build and send a JobRequest, and return a request ID.

The context and control_extra arguments may be used to include extra values in the
context and control headers, respectively.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service from which to receive responses
  - ``actions`` (``list``) - A list of ``ActionRequest`` objects
  - ``switches`` (``union[list, set]``) - A list of switch value integers
  - ``correlation_id`` (``union[str, unicode]``) - The request correlation ID
  - ``continue_on_error`` (``bool``) - Whether to continue executing further actions once one action has returned errors
  - ``context`` (``dict``) - A dictionary of extra values to include in the context header
  - ``control_extra`` (``dict``) - A dictionary of extra values to include in the control header
  - ``message_expiry_in_seconds`` (``int``) - How soon the message will expire if not received by a server (defaults to
    sixty seconds unless the settings are otherwise)
  - ``suppress_response`` (``bool``) - If ``True``, the service will process the request normally but omit the step of
    sending a response back to the client (use this feature to implement send-and-forget
    patterns for asynchronous execution)

Returns
  ``int`` - The request ID

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``


.. _pysoa.client.client.Client.JobError:

``class Client.JobError``
+++++++++++++++++++++++++

**module:** ``pysoa.client.client``

- ``object``

  - ``exceptions.Exception``

    - ``JobError``

Raised by ``Client.call_***`` methods when a job response contains one or more job errors. Stores a list of
``Error`` objects, and has a string representation cleanly displaying the errors.

.. _pysoa.client.client.Client.JobError-constructor-docs:

Constructor
***********

Parameters
  - ``errors`` (``list[Error]``) - The list of all errors in this job, available as an ``errors`` property on the exception
    instance.


.. _pysoa.client.client.Client.CallActionError:

``class Client.CallActionError``
++++++++++++++++++++++++++++++++

**module:** ``pysoa.client.client``

- ``object``

  - ``exceptions.Exception``

    - ``CallActionError``

Raised by ``Client.call_***`` methods when a job response contains one or more action errors. Stores a list of
``ActionResponse`` objects, and has a string representation cleanly displaying the actions' errors.

.. _pysoa.client.client.Client.CallActionError-constructor-docs:

Constructor
***********

Parameters
  - ``actions`` (``list[ActionResponse]``) - The list of all actions that have errors (not actions without errors), available as an
    ``actions`` property on the exception instance.


.. _pysoa.client.client.Client.FutureResponse:

``class Client.FutureResponse``
+++++++++++++++++++++++++++++++

**module:** ``pysoa.client.client``

- ``object``

  - ``FutureResponse``

A future representing a retrievable response after sending a request.

.. _pysoa.client.client.Client.FutureResponse-constructor-docs:

Constructor
***********

*(No documentation)*

.. _pysoa.client.client.Client.FutureResponse.done:

``method done()``
*****************

Returns ``False`` if the response (or exception) has not yet been obtained, ``True`` otherwise.

Returns
  Whether the request is known to be done (this is updated only when ``result`` or ``exception`` is
called).

.. _pysoa.client.client.Client.FutureResponse.exception:

``method exception(timeout=None)``
**********************************

Obtain the exception raised by the call, blocking if necessary, per the rules specified in the
documentation for ``result``. If the call completed without raising an exception, ``None`` is returned. If a
timeout occurs, ``MessageReceiveTimeout`` will be raised (not returned).

Parameters
  - ``timeout`` (``int``) - If specified, the client will block for at most this many seconds waiting for a response.
    If not specified, but a timeout was specified when calling the request method, the client
    will block for at most that many seconds waiting for a response. If neither this nor the
    request method timeout are specified, the configured timeout setting (or default of 5
    seconds) will be used.

Returns
  ``Exception`` - The exception

.. _pysoa.client.client.Client.FutureResponse.result:

``method result(timeout=None)``
*******************************

Obtain the result of this future response.

The first time you call this method on a given future response, it will block for a response and then
either return the response or raise any errors raised by the response. You can specify an optional timeout,
which will override any timeout specified in the client settings or when calling the request method. If a
timeout occurs, ``MessageReceiveTimeout`` will be raised. It will not be cached, and you can attempt to call
this again, and those subsequent calls to ``result`` (or ``exception``) will be treated like a first-time calls
until a response is returned or non-timeout error is raised.

The subsequent times you call this method on a given future response after obtaining a non-timeout response,
any specified timeout will be ignored, and the cached response will be returned (or the cached exception
re-raised).

Parameters
  - ``timeout`` (``int``) - If specified, the client will block for at most this many seconds waiting for a response.
    If not specified, but a timeout was specified when calling the request method, the client
    will block for at most that many seconds waiting for a response. If neither this nor the
    request method timeout are specified, the configured timeout setting (or default of 5
    seconds) will be used.

Returns
  ``union[ActionResponse, JobResponse, list[union[ActionResponse, JobResponse]], generator[union[ActionResponse, JobResponse]]]`` - The response

.. _pysoa.client.client.Client.FutureResponse.running:

``method running()``
********************

Returns ``True`` if the response (or exception) has not yet been obtained, ``False`` otherwise.

Returns
  Whether the request is believed to still be running (this is updated only when ``result`` or
``exception`` is called).


.. _pysoa.client.client.ServiceHandler:

``class ServiceHandler``
++++++++++++++++++++++++

**module:** ``pysoa.client.client``

- ``object``

  - ``ServiceHandler``

Does the low-level work of communicating with an individual service through its configured transport.

.. _pysoa.client.client.ServiceHandler-constructor-docs:

Constructor
***********

Parameters
  - ``service_name`` - The name of the service which this handler calls
  - ``settings`` - The client settings object for this service (and only this service)

.. _pysoa.client.client.ServiceHandler.get_all_responses:

``method get_all_responses(receive_timeout_in_seconds=None)``
*************************************************************

Receive all available responses from the transport as a generator.

Parameters
  - ``receive_timeout_in_seconds`` (``int``) - How long to block without receiving a message before raising
    ``MessageReceiveTimeout`` (defaults to five seconds unless the settings are
    otherwise).

Returns
  ``generator`` - A generator that yields (request ID, job response)

Raises
  ``ConnectionError``, ``MessageReceiveError``, ``MessageReceiveTimeout``, ``InvalidMessage``, ``StopIteration``

.. _pysoa.client.client.ServiceHandler.send_request:

``method send_request(job_request, message_expiry_in_seconds=None)``
********************************************************************

Send a JobRequest, and return a request ID.

The context and control_extra arguments may be used to include extra values in the
context and control headers, respectively.

Parameters
  - ``job_request`` (``JobRequest``) - The job request object to send
  - ``message_expiry_in_seconds`` (``int``) - How soon the message will expire if not received by a server (defaults to
    sixty seconds unless the settings are otherwise)

Returns
  ``int`` - The request ID

Raises
  ``ConnectionError``, ``InvalidField``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``


.. _pysoa.client.expander.ExpansionSettings

``settings schema class ExpansionSettings``
+++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.client.expander``

Defines the schema for configuration settings used when expanding objects on responses with the Expansions tool.

Settings Schema Definition
**************************

- ``type_expansions`` - flexible ``dict``: The definition of all types that may contain identifiers that can be expanded into objects using the ``type_routes`` configurations

  keys
    ``unicode``: The name of the type for which the herein defined expansions can be sought, which will be matched with a key from the ``expansions`` dict passed to one of ``Client``'s ``call_***`` methods, and which must also match the value of a ``_type`` field found on response objects on which extra data will be expanded

  values
    flexible ``dict``: The definition of all possible expansions for this object type

    keys
      ``unicode``: The name of an expansion, which will be matched with a value from the ``expansions`` dict passed to one of ``Client``'s ``call_***`` methods corresponding to the type key in that dict

    values
      strict ``dict``: The definition of one specific possible expansion for this object type

      - ``destination_field`` - ``unicode``: The name of a not-already-existent field in the base object into which the expansion object will be placed after it is obtained from the route
      - ``raise_action_errors`` - ``boolean``: Whether to raise action errors encountered when expanding objects these objects (by default, action errors are suppressed, which differs from the behavior of the ``Client`` to raise action errors during normal requests)
      - ``route`` - ``unicode``: The route to use to resolve this expansion, which must match a key in the ``type_routes`` configuration
      - ``source_field`` - ``unicode``: The name of the field in the base object that contains the identifier used for obtaining the expansion object (the identifier will be passed to the ``request_field`` in the route when resolving the expansion)
      - ``type`` - ``unicode`` (nullable): The type of object this expansion yields, which must map back to a ``type_expansions`` key in order to support nested/recursive expansions, and may be ``None`` if you do not wish to support nested/recursive expansions for this expansion

      Optional keys: ``raise_action_errors``



- ``type_routes`` - flexible ``dict``: The definition of all recognized types that can be expanded into and information about how to resolve objects of those types through action calls

  keys
    ``unicode``: The name of the expansion route, to be referenced from the ``type_expansions`` configuration

  values
    strict ``dict``: The instructions for resolving this type route

    - ``action`` - ``unicode``: The name of the action to call to resolve this route, which must accept a single request field of type ``List``, to which all the identifiers for matching candidate expansions will be passed, and which must return a single response field of type ``Dictionary``, from which all expansion objects will be obtained
    - ``request_field`` - ``unicode``: The name of the ``List`` identifier field to place in the ``ActionRequest`` body when making the request to the named service and action
    - ``response_field`` - ``unicode``: The name of the ``Dictionary`` field returned in the ``ActionResponse``, from which the expanded objects will be extracted
    - ``service`` - ``unicode``: The name of the service to call to resolve this route


.. _pysoa.client.middleware.ClientMiddleware:

``class ClientMiddleware``
++++++++++++++++++++++++++

**module:** ``pysoa.client.middleware``

- ``object``

  - ``ClientMiddleware``

Base middleware class for client middleware. Not required, but provides some helpful stubbed methods and
documentation that you should follow for creating your middleware classes. If you extend this class, you may
override either one or both of the methods.

Middleware must have two callable attributes, ``request`` and ``response``, that, when called with the next level
down, return a callable that takes the appropriate arguments and returns the appropriate value.

.. _pysoa.client.middleware.ClientMiddleware.request:

``method request(send_request)``
********************************

In sub-classes, used for creating a wrapper around ``send_request``. In this simple implementation, just
returns ``send_request``.

Parameters
  - ``send_request`` (``callable(int, dict, JobRequest, int): undefined``) - A callable that accepts a request ID int, meta ``dict``, ``JobRequest`` object, and
    message expiry int and returns nothing

Returns
  ``callable(int, dict, JobRequest, int): undefined`` - A callable that accepts a request ID int, meta ``dict``, ``JobRequest`` object, and message expiry int
and returns nothing.

.. _pysoa.client.middleware.ClientMiddleware.response:

``method response(get_response)``
*********************************

In sub-classes, used for creating a wrapper around ``get_response``. In this simple implementation, just
returns ``get_response``.

Parameters
  - ``get_response`` (``callable(int): tuple<int, JobResponse>``) - A callable that accepts a timeout int and returns tuple of request ID int and
    ``JobResponse`` object

Returns
  ``callable(int): tuple<int, JobResponse>`` - A callable that accepts a timeout int and returns tuple of request ID int and ``JobResponse`` object.


.. _pysoa.client.settings.PolymorphicClientSettings

``settings schema class PolymorphicClientSettings``
+++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.client.settings``

Settings for Clients that can use any type of transport, while performing validation on certain transport types.

Settings Schema Definition
**************************

- ``metrics`` - strict ``dict``: Configuration for defining a usage and performance metrics recorder

  - ``kwargs`` - strict ``dict``: The keyword arguments that will be passed to the constructed metrics recorder

    - ``config`` - flexible ``dict``: Whatever metrics configuration is required

      keys
        ``hashable``: *(no description)*

      values
        ``anything``: *(no description)*


    Extra keys of any value are allowed. Optional keys: ``config``

  - ``path`` - ``unicode``: The path to the class extending ``MetricsRecorder``, in the format ``module.name:ClassName``

  Optional keys: ``kwargs``

- ``middleware`` - ``list``: The list of all ``ClientMiddleware`` objects that should be applied to requests made from this client to the associated service

  values
    strict ``dict``: *(no description)*

    - ``kwargs`` - flexible ``dict``: Any keyword arguments that should be passed to the class when constructing a new instance

      keys
        ``unicode``: *(no description)*

      values
        ``anything``: *(no description)*

    - ``path`` - ``unicode``: The path to the class to be imported and used, in the format ``module.name:ClassName``

    Optional keys: ``kwargs``

- ``transport`` - dictionary whose schema switches based on the value of ``path``, dynamically based on class imported from ``path`` (see the settings schema documentation for the class named at ``path``){}
- ``transport_cache_time_in_seconds`` - ``anything``: This field is deprecated. The transport cache is no longer supported. This settings field will remain in place until 2018-06-15 to give a safe period for people to remove it from settings, but its value will always be ignored.

Default Values
**************

Keys present in the dict below can be omitted from compliant settings dicts, in which case the values below will
apply as the default values.

.. code-block:: python

    {
        "metrics": {
            "path": "pysoa.common.metrics:NoOpMetricsRecorder"
        },
        "middleware": [],
        "transport": {
            "path": "pysoa.common.transport.redis_gateway.client:RedisClientTransport"
        },
        "transport_cache_time_in_seconds": 0
    }


.. _pysoa.common.metrics.Counter:

``abstract class Counter``
++++++++++++++++++++++++++

**module:** ``pysoa.common.metrics``

- ``object``

  - ``Counter``

Defines an interface for incrementing a counter.

.. _pysoa.common.metrics.Counter.increment:

``method increment(amount=1)``
******************************

Increments the counter.

Parameters
  - ``amount`` - The amount by which to increment the counter, which must default to 1.


.. _pysoa.common.metrics.MetricsRecorder:

``abstract class MetricsRecorder``
++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.metrics``

- ``object``

  - ``MetricsRecorder``

Defines an interface for recording metrics. All metrics recorders registered with PySOA must implement this
interface. Note that counters and timers with the same name will not be recorded. If your metrics backend needs
timers to also have associated counters, your implementation of this recorder must take care of filling that gap.

.. _pysoa.common.metrics.MetricsRecorder.commit:

``method commit()``
*******************

Commits the recorded metrics, if necessary, to the storage medium in which they reside. Can simply be a
no-op if metrics are recorded immediately.

.. _pysoa.common.metrics.MetricsRecorder.counter:

``method counter(name, **kwargs)``
**********************************

Returns a counter that can be incremented. Implementations do not have to return an instance of ``Counter``, but
they must at least return an object that matches the interface for ``Counter``.

Parameters
  - ``name`` - The name of the counter
  - ``kwargs`` - Any other arguments that may be needed

Returns
  ``Counter`` - a counter object.

.. _pysoa.common.metrics.MetricsRecorder.timer:

``method timer(name, resolution=TimerResolution.MILLISECONDS, **kwargs)``
*************************************************************************

Returns a timer that can be started and stopped. Implementations do not have to return an instance of ``Timer``,
but they must at least return an object that matches the interface for ``Timer``, including serving as a context
manager.

Parameters
  - ``name`` - The name of the timer
  - ``resolution`` (``enum.IntEnum``) - The resolution at which this timer should operate, defaulting to milliseconds. Its value
    should be a ``TimerResolution`` or any other equivalent ``IntEnum`` whose values serve as
    integer multipliers to convert decimal seconds to the corresponding units. It will only
    ever be access as a keyword argument, never as a positional argument, so it is not necessary
    for this to be the second positional argument in your equivalent recorder class.
  - ``kwargs`` - Any other arguments that may be needed

Returns
  ``Timer`` - a timer object


.. _pysoa.common.metrics.NoOpMetricsRecorder:

``class NoOpMetricsRecorder``
+++++++++++++++++++++++++++++

**module:** ``pysoa.common.metrics``

- ``object``

  - `pysoa.common.metrics.MetricsRecorder`_

    - ``NoOpMetricsRecorder``

A dummy metrics recorder that doesn't actually record any metrics and has no overhead, used when no
metrics-recording settings have been configured.

.. _pysoa.common.metrics.NoOpMetricsRecorder-constructor-docs:

Constructor
***********

A dummy constructor that ignores all arguments

.. _pysoa.common.metrics.NoOpMetricsRecorder.commit:

``method commit()``
*******************

Does nothing

.. _pysoa.common.metrics.NoOpMetricsRecorder.counter:

``method counter(name, **kwargs)``
**********************************

Returns a counter that does nothing.

Parameters
  - ``name`` - Unused

Returns
  ``NoOpMetricsRecorder.NoOpCounter`` - A do-nothing counter

.. _pysoa.common.metrics.NoOpMetricsRecorder.timer:

``method timer(name, **kwargs)``
********************************

Returns a timer that does nothing.

Parameters
  - ``name`` - Unused

Returns
  ``NoOpMetricsRecorder.NoOpTimer`` - A do-nothing timer


.. _pysoa.common.metrics.Timer:

``abstract class Timer``
++++++++++++++++++++++++

**module:** ``pysoa.common.metrics``

- ``object``

  - ``Timer``

Defines an interface for timing activity. Can be used as a context manager to time wrapped activity.

.. _pysoa.common.metrics.Timer.__enter__:

``method __enter__()``
**********************

Starts the timer at the start of the context manager.

.. _pysoa.common.metrics.Timer.__exit__:

``method __exit__(*_, **__)``
*****************************

Stops the timer at the end of the context manager. All parameters are ignored. Always returns ``False``.

Returns
  ``bool`` - ``False``

.. _pysoa.common.metrics.Timer.start:

``method start()``
******************

Starts the timer.

.. _pysoa.common.metrics.Timer.stop:

``method stop()``
*****************

Stops the timer.


.. _pysoa.common.metrics.TimerResolution:

``enum TimerResolution``
++++++++++++++++++++++++

**module:** ``pysoa.common.metrics``

Constant Values:

- ``MILLISECONDS`` (``1000``)
- ``MICROSECONDS`` (``1000000``)
- ``NANOSECONDS`` (``1000000000``)


.. _pysoa.common.transport.base.ClientTransport:

``abstract class ClientTransport``
++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.base``

- ``object``

  - ``ClientTransport``

.. _pysoa.common.transport.base.ClientTransport-constructor-docs:

Constructor
***********

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service to which this transport will send requests (and from which it will
    receive responses)
  - ``metrics`` (``MetricsRecorder``) - The optional metrics recorder

.. _pysoa.common.transport.base.ClientTransport.receive_response_message:

``method receive_response_message(receive_timeout_in_seconds=None)``
********************************************************************

Receive a response message from the backend and return a 3-tuple of (request_id, meta dict, message dict).

Parameters
  - ``receive_timeout_in_seconds`` (``int``) - How long to block waiting for a response to become available
    (implementations should provide a sane default or setting for default)

Returns
  ``tuple`` - A tuple of the request ID, meta dict, and message dict, in that order

Raises
  ``ConnectionError``, ``MessageReceiveError``, ``MessageReceiveTimeout``

.. _pysoa.common.transport.base.ClientTransport.send_request_message:

``method send_request_message(request_id, meta, body, message_expiry_in_seconds=None)``
***************************************************************************************

Send a request message.

Parameters
  - ``request_id`` (``int``) - The request ID
  - ``meta`` (``dict``) - Meta information about the message
  - ``body`` (``dict``) - The message body
  - ``message_expiry_in_seconds`` (``int``) - How soon the message should expire if not retrieved by a server
    (implementations should provide a sane default or setting for default)

Raises
  ``ConnectionError``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``


.. _pysoa.common.transport.base.ServerTransport:

``abstract class ServerTransport``
++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.base``

- ``object``

  - ``ServerTransport``

.. _pysoa.common.transport.base.ServerTransport-constructor-docs:

Constructor
***********

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service for which this transport will receive requests and send responses
  - ``metrics`` (``MetricsRecorder``) - The optional metrics recorder

.. _pysoa.common.transport.base.ServerTransport.receive_request_message:

``method receive_request_message()``
************************************

Receive a request message from the backend and return a 3-tuple of (request_id, meta dict, message dict). The
metadata may include client reply-to information that should be passed back to send_response_message.

Returns
  ``tuple`` - A tuple of the request ID, meta dict, and message dict, in that order

Raises
  ``ConnectionError``, ``MessageReceiveError``, ``MessageReceiveTimeout``

.. _pysoa.common.transport.base.ServerTransport.send_response_message:

``method send_response_message(request_id, meta, body)``
********************************************************

Send a response message. The meta dict returned by receive_request_message should be passed verbatim as the
second argument.

Parameters
  - ``request_id`` (``int``) - The request ID
  - ``meta`` (``dict``) - Meta information about the message
  - ``body`` (``dict``) - The message body

Raises
  ``ConnectionError``, ``MessageSendError``, ``MessageSendTimeout``, ``MessageTooLarge``


.. _pysoa.common.transport.local.LocalClientTransport:

``class LocalClientTransport``
++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.local``

- ``object``

  - `pysoa.common.transport.base.ClientTransport`_

    - ``LocalClientTransport``

A transport that incorporates a server for running a service and client in a single thread.

.. _pysoa.common.transport.local.LocalClientTransport-constructor-docs:

Constructor
***********

Parameters
  - ``service_name`` (``union[str, unicode]``) - The service name
  - ``metrics`` (``MetricsRecorder``) - The metrics recorder
  - ``server_class`` (``class``) - The server class for which this transport will serve as a client
  - ``server_settings`` (``dict``) - The server settings that will be passed to the server class on instantiation

.. _pysoa.common.transport.local.LocalClientTransport.receive_request_message:

``method receive_request_message()``
************************************

Gives the server the current request (we are actually inside the stack of send_request_message so we know this
is OK).

.. _pysoa.common.transport.local.LocalClientTransport.receive_response_message:

``method receive_response_message(_=None)``
*******************************************

Receives a message from the deque. ``receive_timeout_in_seconds`` is not supported. Receive does not time out,
because by the time the thread calls this method, a response is already available in the deque, or something
happened and a response will never be available. This method does not wait and returns immediately.

Parameters
  - ``_``

.. _pysoa.common.transport.local.LocalClientTransport.send_request_message:

``method send_request_message(request_id, meta, body, _=None)``
***************************************************************

Receives a request from the client and handles and dispatches in in-thread. ``message_expiry_in_seconds`` is not
supported. Messages do not expire, as the server handles the request immediately in the same thread before
this method returns. This method blocks until the server has completed handling the request.

Parameters
  - ``request_id``
  - ``meta``
  - ``body``
  - ``_``

.. _pysoa.common.transport.local.LocalClientTransport.send_response_message:

``method send_response_message(request_id, meta, body)``
********************************************************

Add the response to the deque.

Parameters
  - ``request_id``
  - ``meta``
  - ``body``


.. _pysoa.common.transport.local.LocalClientTransportSchema

``class-path settings schema LocalClientTransportSchema``
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.local``

Settings Schema Definition
**************************
strict ``dict``: The settings for the local client transport

- ``kwargs`` - strict ``dict``: *(no description)*

  - ``server_class`` - any of the types bulleted below: The path to the ``Server`` class to use locally (as a library), or a reference to the ``Server``-extending class/type itself

    - ``unicode``: The path to the ``Server`` class, in the format ``module.name:ClassName``
    - ``object_instance``: A reference to the ``Server``-extending class/type (additional information: ``{u'valid_type': "(<type 'type'>, <type 'classobj'>)"}``)

  - ``server_settings`` - flexible ``dict``: The settings to use when instantiating the ``server_class``

    keys
      ``unicode``: *(no description)*

    values
      ``anything``: *(no description)*


- ``path`` - ``unicode``: The path to the local client transport, in the format ``module.name:ClassName``


.. _pysoa.common.transport.local.LocalServerTransport:

``class LocalServerTransport``
++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.local``

- ``object``

  - `pysoa.common.transport.base.ServerTransport`_

    - ``LocalServerTransport``

Empty class that we use as an import stub for local transport before we swap in the Client transport instance to do
double duty.

.. _pysoa.common.transport.local.LocalServerTransport.receive_request_message:

``method receive_request_message()``
************************************

Does nothing, because this will never be called (the same-named method on the ``LocalClientTransport`` is called,
instead).

.. _pysoa.common.transport.local.LocalServerTransport.send_response_message:

``method send_response_message(request_id, meta, body)``
********************************************************

Does nothing, because this will never be called (the same-named method on the ``LocalClientTransport`` is called,
instead).

Parameters
  - ``request_id``
  - ``meta``
  - ``body``


.. _pysoa.common.transport.local.LocalServerTransportSchema

``class-path settings schema LocalServerTransportSchema``
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.local``

Settings Schema Definition
**************************
strict ``dict``: The settings for the local client transport

- ``kwargs`` - strict ``dict``: *(no description)*


- ``path`` - ``unicode``: The path to the local server transport, in the format ``module.name:ClassName``

Optional keys: ``kwargs``


.. _pysoa.common.transport.redis_gateway.client.RedisClientTransport:

``class RedisClientTransport``
++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.redis_gateway.client``

- ``object``

  - `pysoa.common.transport.base.ClientTransport`_

    - ``RedisClientTransport``

.. _pysoa.common.transport.redis_gateway.client.RedisClientTransport-constructor-docs:

Constructor
***********

In addition to the two named positional arguments, this constructor expects keyword arguments abiding by the
Redis transport settings schema.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service to which this transport will send requests (and from which it will
    receive responses)
  - ``metrics`` (``MetricsRecorder``) - The optional metrics recorder

.. _pysoa.common.transport.redis_gateway.client.RedisClientTransport.receive_response_message:

``method receive_response_message(receive_timeout_in_seconds=None)``
********************************************************************

*(No documentation)*

.. _pysoa.common.transport.redis_gateway.client.RedisClientTransport.requests_outstanding:

``property requests_outstanding``
*********************************

Indicates the number of requests currently outstanding, which still need to be received. If this value is less
than 1, calling ``receive_response_message`` will result in a return value of ``(None, None, None)`` instead of
raising a ``MessageReceiveTimeout``.

*(Property is read-only)*

.. _pysoa.common.transport.redis_gateway.client.RedisClientTransport.send_request_message:

``method send_request_message(request_id, meta, body, message_expiry_in_seconds=None)``
***************************************************************************************

*(No documentation)*


.. _pysoa.common.transport.redis_gateway.server.RedisServerTransport:

``class RedisServerTransport``
++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.redis_gateway.server``

- ``object``

  - `pysoa.common.transport.base.ServerTransport`_

    - ``RedisServerTransport``

.. _pysoa.common.transport.redis_gateway.server.RedisServerTransport-constructor-docs:

Constructor
***********

In addition to the two named positional arguments, this constructor expects keyword arguments abiding by the
Redis transport settings schema.

Parameters
  - ``service_name`` (``union[str, unicode]``) - The name of the service for which this transport will receive requests and send responses
  - ``metrics`` (``MetricsRecorder``) - The optional metrics recorder

.. _pysoa.common.transport.redis_gateway.server.RedisServerTransport.receive_request_message:

``method receive_request_message()``
************************************

*(No documentation)*

.. _pysoa.common.transport.redis_gateway.server.RedisServerTransport.send_response_message:

``method send_response_message(request_id, meta, body)``
********************************************************

*(No documentation)*


.. _pysoa.common.transport.redis_gateway.settings.RedisTransportSchema

``class-path settings schema RedisTransportSchema``
+++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.common.transport.redis_gateway.settings``

Settings Schema Definition
**************************
strict ``dict``: The settings for the Redis transport

- ``kwargs`` - strict ``dict``: *(no description)*

  - ``backend_layer_kwargs`` - strict ``dict``: The arguments passed to the Redis connection manager

    - ``connection_kwargs`` - flexible ``dict``: The arguments used when creating all Redis connections (see Redis-Py docs)

      keys
        ``hashable``: *(no description)*

      values
        ``anything``: *(no description)*

    - ``hosts`` - ``list``: The list of Redis hosts, where each is a tuple of ``("address", port)`` or the simple string address.

      values
        any of the types bulleted below: *(no description)*

        - ``tuple``: *(no description)* (additional information: ``{u'contents': [{u'type': u'unicode'}, {u'type': u'integer'}]}``)
        - ``unicode``: *(no description)*

    - ``redis_db`` - ``integer``: The Redis database, a shortcut for putting this in ``connection_kwargs``.
    - ``redis_port`` - ``integer``: The port number, a shortcut for putting this on all hosts
    - ``sentinel_failover_retries`` - ``integer``: How many times to retry (with a delay) getting a connection from the Sentinel when a master cannot be found (cluster is in the middle of a failover); should only be used for Sentinel backend type
    - ``sentinel_services`` - ``list``: A list of Sentinel services (will be discovered by default); should only be used for Sentinel backend type

      values
        ``unicode``: *(no description)*

    Optional keys: ``connection_kwargs``, ``hosts``, ``redis_db``, ``redis_port``, ``sentinel_failover_retries``, ``sentinel_services``

  - ``backend_type`` - ``constant``: Which backend (standard or sentinel) should be used for this Redis transport (additional information: ``{u'values': [u'redis.standard', u'redis.sentinel']}``)
  - ``default_serializer_config`` - strict ``dict``: The configuration for the serializer this transport should use

    - ``kwargs`` - flexible ``dict``: Any keyword arguments that should be passed to the class when constructing a new instance

      keys
        ``unicode``: *(no description)*

      values
        ``anything``: *(no description)*

    - ``path`` - ``unicode``: The path to the class to be imported and used, in the format ``module.name:ClassName``

    Optional keys: ``kwargs``

  - ``log_messages_larger_than_bytes`` - ``integer``: By default, messages larger than 100KB that do not trigger errors (see ``maximum_message_size_in_bytes``) will be logged with level WARNING to a logger named ``pysoa.transport.oversized_message``. To disable this behavior, set this setting to 0. Or, you can set it to some other number to change the threshold that triggers logging.
  - ``maximum_message_size_in_bytes`` - ``integer``: The maximum message size, in bytes, that is permitted to be transmitted over this transport (defaults to 100KB on the client and 250KB on the server)
  - ``message_expiry_in_seconds`` - ``integer``: How long after a message is sent that it is considered expired, dropped from queue
  - ``queue_capacity`` - ``integer``: The capacity of the message queue to which this transport will send messages
  - ``queue_full_retries`` - ``integer``: How many times to retry sending a message to a full queue before giving up
  - ``receive_timeout_in_seconds`` - ``integer``: How long to block waiting on a message to be received

  Optional keys: ``backend_layer_kwargs``, ``default_serializer_config``, ``log_messages_larger_than_bytes``, ``maximum_message_size_in_bytes``, ``message_expiry_in_seconds``, ``queue_capacity``, ``queue_full_retries``, ``receive_timeout_in_seconds``

- ``path`` - ``unicode``: The path to the Redis client or server transport, in the format ``module.name:ClassName``


.. _pysoa.common.types.ActionRequest:

``class ActionRequest``
+++++++++++++++++++++++

**module:** ``pysoa.common.types``

- ``object``

  - ``ActionRequest``

A request that the server execute a single action.

.. _pysoa.common.types.ActionRequest-attrs-docs:

Attrs Properties
****************

- ``action`` (required)
- ``body``


.. _pysoa.common.types.ActionResponse:

``class ActionResponse``
++++++++++++++++++++++++

**module:** ``pysoa.common.types``

- ``object``

  - ``ActionResponse``

A response generated by a single action on the server.

.. _pysoa.common.types.ActionResponse-attrs-docs:

Attrs Properties
****************

- ``action`` (required)
- ``errors``
- ``body``


.. _pysoa.common.types.Error:

``class Error``
+++++++++++++++

**module:** ``pysoa.common.types``

- ``object``

  - ``Error``

The error generated by a single action.

.. _pysoa.common.types.Error-attrs-docs:

Attrs Properties
****************

- ``code`` (required)
- ``message`` (required)
- ``field``
- ``traceback``
- ``variables``
- ``denied_permissions``


.. _pysoa.common.types.JobRequest:

``class JobRequest``
++++++++++++++++++++

**module:** ``pysoa.common.types``

- ``object``

  - ``JobRequest``

A request that the server execute a job.

A job consists of one or more actions and a control header. Each action is an ActionRequest,
while the control header is a dictionary.

.. _pysoa.common.types.JobRequest-attrs-docs:

Attrs Properties
****************

- ``control``
- ``context``
- ``actions``


.. _pysoa.common.types.JobResponse:

``class JobResponse``
+++++++++++++++++++++

**module:** ``pysoa.common.types``

- ``object``

  - ``JobResponse``

A response generated by a server job.

Contains the result or error generated by each action in the job.

.. _pysoa.common.types.JobResponse-attrs-docs:

Attrs Properties
****************

- ``errors``
- ``context``
- ``actions``


.. _pysoa.server.action.base.Action:

``abstract class Action``
+++++++++++++++++++++++++

**module:** ``pysoa.server.action.base``

- ``object``

  - ``Action``

Base class from which all SOA service actions inherit.

Contains the basic framework for implementing an action:

- Subclass and override ``run()`` with the body of your code
- Optionally provide a ``description`` attribute, which should be a unicode string and is used to display
  introspection for the action.
- Optionally provide ``request_schema`` and/or ``response_schema`` attributes. These should be Conformity fields.
- Optionally provide a ``validate()`` method to do custom validation on the request.

.. _pysoa.server.action.base.Action-constructor-docs:

Constructor
***********

Construct a new action. Concrete classes can override this and define a different interface, but they must
still pass the server settings to this base constructor by calling ``super``.

Parameters
  - ``settings`` (``dict``) - The server settings object

.. _pysoa.server.action.base.Action.__call__:

``method __call__(action_request)``
***********************************

Main entry point for actions from the ``Server`` (or potentially from tests). Validates that the request matches
the ``request_schema``, then calls ``validate()``, then calls ``run()`` if ``validate()`` raised no errors, and then
validates that the return value from ``run()`` matches the ``response_schema`` before returning it in an
``ActionResponse``.

Parameters
  - ``action_request`` (``EnrichedActionRequest``) - The request object

Returns
  ``ActionResponse`` - The response object

Raises
  ``ActionError``, ``ResponseValidationError``

.. _pysoa.server.action.base.Action.run:

``method run(request)``
***********************

Override this to perform your business logic, and either return a value abiding by the ``response_schema`` or
raise an ``ActionError``.

Parameters
  - ``request`` (``EnrichedActionRequest``) - The request object

Returns
  ``dict`` - The response

Raises
  ``ActionError``

.. _pysoa.server.action.base.Action.validate:

``method validate(request)``
****************************

Override this to perform custom validation logic before the ``run()`` method is run. Raise ``ActionError`` if you
find issues, otherwise return (the return value is ignored). If this method raises an error, ``run()`` will not
be called. You do not have to override this method if you don't want to perform custom validation or prefer to
perform it in ``run()``.

Parameters
  - ``request`` (``EnrichedActionRequest``) - The request object

Raises
  ``ActionError``


.. _pysoa.server.action.introspection.IntrospectionAction:

``class IntrospectionAction``
+++++++++++++++++++++++++++++

**module:** ``pysoa.server.action.introspection``

- ``object``

  - `pysoa.server.action.base.Action`_

    - ``IntrospectionAction``

This action returns detailed information about the service's defined actions and the request and response schemas
for each action, along with any documentation defined for the action or for the service itself. It can be passed
a single action name to return information limited to that single action. Otherwise, it will return information for
all of the service's actions.

This action will be added to your service on your behalf if you do not define an action with name ``introspect``.

Making your services and actions capable of being introspected is simple. If your server class has a ``description``
attribute, that will be the service's documentation that introspection returns. If your server class does not have
this attribute but does have a docstring, introspection will use the docstring. The same rule applies to action
classes: Introspection first looks for a ``description`` attribute and then uses the docstring, if any. If neither of
these are found, the applicable service or action documentation will be done.

Introspection then looks at the ``request_schema`` and ``response_schema`` attributes for each of your actions, and
includes the details about these schemas in the returned information for each action. Be sure you include field
descriptions in your schema for the most effective documentation possible.

.. _pysoa.server.action.introspection.IntrospectionAction-constructor-docs:

Constructor
***********

Construct a new introspection action. Unlike its base class, which accepts a server settings object, this
must be passed a ``Server`` object, from which it will obtain a settings object. The ``Server`` code that calls
this action has special handling to address this requirement.

Parameters
  - ``server`` (``Server``) - A PySOA server instance

.. _pysoa.server.action.introspection.IntrospectionAction.run:

``method run(request)``
***********************

Introspects all of the actions on the server and returns their documentation.

Parameters
  - ``request`` (``EnrichedActionRequest``) - The request object

Returns
  The response


.. _pysoa.server.action.status.BaseStatusAction:

``abstract class BaseStatusAction``
+++++++++++++++++++++++++++++++++++

**module:** ``pysoa.server.action.status``

- ``object``

  - `pysoa.server.action.base.Action`_

    - ``BaseStatusAction``

Standard base action for status checks. Returns health check and version information.

If you want to use the status action use ``StatusActionFactory(version)``, passing in the version of your service
and, optionally, the build of your service. If you do not specify an action with name ``status`` in your server,
this will be done on your behalf.

If you want to make a custom status action, subclass this class, make ``self._version`` return your service's version
string, ``self._build`` optionally return your service's build string, and add any additional health check methods
you desire. Health check methods must start with ``check_``.

Health check methods accept a single argument, the request object (an instance of ``ActionRequest``), and return a
list of tuples in the format ``(is_error, code, description)`` (or a false-y value if there are no problems):

- ``is_error``: ``True`` if this is an error, ``False`` if it is a warning.
- ``code``: Invariant string for this error, like "MYSQL_FAILURE"
- ``description``: Human-readable description of the problem, like "Could not connect to host on port 1234"

Health check methods can also write to the ``self.diagnostics`` dictionary to add additional data which will be sent
back with the response if they like. They are responsible for their own key management in this situation.

This base status action comes with a disabled-by-default health check method named ``_check_client_settings`` (the
leading underscore disables it), which calls ``status`` on all other services that this service is configured to call
(using ``verbose: False``, which guarantees no further recursive status checking) and includes those responses in
this action's response. To enable this health check, simply reference it as a new, valid ``check_`` method name, like
so:

.. code:: python

    class MyStatusAction(BaseStatusAction):
        ...
        check_client_settings = BaseStatusAction._check_client_settings

.. _pysoa.server.action.status.BaseStatusAction-constructor-docs:

Constructor
***********

Constructs a new base status action. Concrete status actions can override this if they want, but must call
``super``.

Parameters
  - ``settings`` (``dict``) - The server settings object

.. _pysoa.server.action.status.BaseStatusAction.run:

``method run(request)``
***********************

Adds version information for Conformity, PySOA, Python, and the service to the response, then scans the class
for ``check_`` methods and runs them (unless ``verbose`` is ``False``).

Parameters
  - ``request`` (``EnrichedActionRequest``) - The request object

Returns
  The response


.. _pysoa.server.action.status.StatusActionFactory:

``function StatusActionFactory(version, build=None, base_class=BaseStatusAction)``
+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.server.action.status``

A factory for creating a new status action class specific to a service.

Parameters
  - ``version`` (``union[str, unicode]``) - The service version
  - ``build`` (``union[str, unicode]``) - The optional service build identifier
  - ``base_class`` (``BaseStatusAction``) - The optional base class, to override ``BaseStatusAction`` as the base class

Returns
  ``class`` - A class named ``StatusAction``, extending ``base_class``, with version and build matching the input parameters


.. _pysoa.server.action.switched.SwitchedAction:

``class SwitchedAction``
++++++++++++++++++++++++

**module:** ``pysoa.server.action.switched``

- ``object``

  - ``SwitchedAction``

A specialized action that defers to other, concrete actions based on request switches. Subclasses must not
override any methods and must override ``switch_to_action_map``. ``switch_to_action_map`` should be some iterable
object that provides ``__len__`` (such as a tuple [recommended] or list). Its items must be indexable objects that
provide ``__len__`` (such as a tuple [recommended] or list) and have exactly two elements.

For each item in ``switch_to_action_map``, the first element must be a switch that provides ``__int__`` (such as an
actual integer) or a switch that provides an attribute ``value`` which, itself, provides ``__int__`` (or is an int).
The second element must be an action, such as an action class (e.g. one that extends ``Action``) or any callable
that accepts a server settings object and returns a new callable that, itself, accepts an ``ActionRequest`` object
and returns an ``ActionResponse`` object or raises an ``ActionError``.

``switch_to_action_map`` must have at least two items in it. ``SwitchedAction`` will iterate over that list, checking
the first element (switch) of each item to see if it is enabled in the request. If it is, the second element (the
action) of that item will be deferred to. If it finds no items whose switches are enabled, it will use the very
last action in ``switch_to_action_map``. As such, you can treat the last item as a default, and its switch could
simply be ``SwitchedAction.DEFAULT_ACTION`` (although, this is not required: it could also be a valid switch, and
it would still be treated as the default in the case that no other items matched).

Example usage:

.. code-block:: python

    class UserActionV1(Action):
        ...

    class UserActionV2(Action):
        ...

    class UserTransitionAction(SwitchedAction):
        switch_to_action_map = (
            (USER_VERSION_2_ENABLED, UserActionV2),
            (SwitchedAction.DEFAULT_ACTION, UserActionV1),
        )

.. _pysoa.server.action.switched.SwitchedAction-constructor-docs:

Constructor
***********

Construct a new action. Concrete classes should not override this.

Parameters
  - ``settings`` (``dict``) - The server settings object

.. _pysoa.server.action.switched.SwitchedAction.__call__:

``method __call__(action_request)``
***********************************

Main entry point for actions from the ``Server`` (or potentially from tests). Finds the appropriate real action
to invoke based on the switches enabled in the request, initializes the action with the server settings, and
then calls the action with the request object, returning its response directly.

Parameters
  - ``action_request`` (``EnrichedActionRequest``) - The request object

Returns
  ``ActionResponse`` - The response object

Raises
  ``ActionError``, ``ResponseValidationError``

.. _pysoa.server.action.switched.SwitchedAction.get_uninitialized_action:

``method get_uninitialized_action(action_request)``
***************************************************

Get the raw action (such as the action class or the base action callable) without instantiating/calling
it, based on the switches in the action request, or the default raw action if no switches were present or
no switches matched.

Parameters
  - ``action_request`` (``EnrichedActionRequest``) - The request object

Returns
  ``callable`` - The action


.. _pysoa.server.middleware.ServerMiddleware:

``class ServerMiddleware``
++++++++++++++++++++++++++

**module:** ``pysoa.server.middleware``

- ``object``

  - ``ServerMiddleware``

Base middleware class for server middleware. Not required, but provides some helpful stubbed methods and
documentation that you should follow for creating your middleware classes. If you extend this class, you may
override either one or both of the methods.

Middleware must have two callable attributes, ``job`` and ``action``, that, when called with the next level down,
return a callable that takes the appropriate arguments and returns the appropriate value.

.. _pysoa.server.middleware.ServerMiddleware.action:

``method action(process_action)``
*********************************

In sub-classes, used for creating a wrapper around ``process_action``. In this simple implementation, just
returns ``process_action``.

Parameters
  - ``process_action`` (``callable(ActionRequest): ActionResponse``) - A callable that accepts an ``ActionRequest`` object and returns an ``ActionResponse``
    object, or errors

Returns
  ``callable(ActionRequest): ActionResponse`` - A callable that accepts an ``ActionRequest`` object and returns an ``ActionResponse`` object, or errors,
by calling the provided ``process_action`` and possibly doing other things.

.. _pysoa.server.middleware.ServerMiddleware.job:

``method job(process_job)``
***************************

In sub-classes, used for creating a wrapper around ``process_job``. In this simple implementation, just returns
'process_job`.

Parameters
  - ``process_job`` (``callable(dict): dict``) - A callable that accepts a job request ``dict`` and returns a job response ``dict``, or errors

Returns
  ``callable(dict): dict`` - A callable that accepts a job request ``dict`` and returns a job response ``dict``, or errors, by calling
the provided ``process_job`` and possibly doing other things.


.. _pysoa.server.server.Server:

``class Server``
++++++++++++++++

**module:** ``pysoa.server.server``

- ``object``

  - ``Server``

The base class from which all PySOA service servers inherit, and contains the code that does all of the heavy
lifting for receiving and handling requests, passing those requests off to the relevant actions, and sending
the actions' responses back to the caller.

Required attributes that all concrete subclasses must provide:

- ``service_name``: A (unicode) string name of the service.
- ``action_class_map``: An object supporting ``__contains__`` and ``__getitem__`` (typically a ``dict``) whose keys are
  action names and whose values are callable objects that return a callable action when called (such as subclasses
  of ``Action`` which, when "called" [constructed], yield a callable object [instance of the subclass])

.. _pysoa.server.server.Server-constructor-docs:

Constructor
***********

Parameters
  - ``settings`` (``ServerSettings``) - The settings object, which must be an instance of ``ServerSettings`` or one of its subclasses

.. _pysoa.server.server.Server.execute_job:

``method execute_job(job_request)``
***********************************

Processes and runs the action requests contained in the job and returns a ``JobResponse``.

Parameters
  - ``job_request`` (``dict``) - The job request

Returns
  ``JobResponse`` - A ``JobResponse`` object

.. _pysoa.server.server.Server.handle_job_error_code:

``method handle_job_error_code(code, message, request_for_logging, response_for_logging, extra=None)``
******************************************************************************************************

*(No documentation)*

.. _pysoa.server.server.Server.handle_job_exception:

``method handle_job_exception(exception, variables=None)``
**********************************************************

Makes and returns a last-ditch error response.

Parameters
  - ``exception`` (``Exception``) - The exception that happened
  - ``variables`` (``dict``) - A dictionary of context-relevant variables to include in the error response

Returns
  ``JobResponse`` - A ``JobResponse`` object

.. _pysoa.server.server.Server.handle_next_request:

``method handle_next_request()``
********************************

Retrieves the next request from the transport, or returns if it times out (no request has been made), and then
processes that request, sends its response, and returns when done.

.. _pysoa.server.server.Server.handle_shutdown_signal:

``method handle_shutdown_signal(*_)``
*************************************

Handles the reception of a shutdown signal.

.. _pysoa.server.server.Server.harakiri:

``method harakiri(*_)``
***********************

Handles the reception of a timeout signal indicating that a request has been processing for too long, as
defined by the Harakiri settings.

.. _pysoa.server.server.Server.initialize:

``static method initialize(settings)``
**************************************

Called just before the ``Server`` class is instantiated, and passed the settings dict. Can be used to perform
settings manipulation, server class patching (such as for performance tracing operations), and more. Use with
great care and caution. Overriding methods must call ``super`` and return ``cls`` or a new/modified ``cls``, which
will be used to instantiate the server. See the documentation for ``Server.main`` for full details on the chain
of ``Server`` method calls.

Parameters
  - ``settings``

Returns
  ``type`` - The server class or a new/modified server class

.. _pysoa.server.server.Server.main:

``static method main()``
************************

Command-line entry point for running a PySOA server. The chain of method calls is as follows::

    cls.main
      |
      -> cls.initialize => new_cls
      -> new_cls.__init__ => self
      -> self.run
          |
          -> self.setup
          -> loop: self.handle_next_request while not self.shutting_down
                    |
                    -> transport.receive_request_message
                    -> self.perform_idle_actions (if no request)
                    -> self.perform_pre_request_actions
                    -> self.process_job
                        |
                        -> middleware(self.execute_job)
                    -> transport.send_response_message
                    -> self.perform_post_request_actions

.. _pysoa.server.server.Server.make_client:

``method make_client(context)``
*******************************

Gets a ``Client`` that will propagate the passed ``context`` in order to to pass it down to middleware or Actions.

Parameters
  - ``context``

Returns
  ``Client`` - A client configured with this server's ``client_routing`` settings

.. _pysoa.server.server.Server.perform_idle_actions:

``method perform_idle_actions()``
*********************************

Runs periodically when the server is idle, if it has been too long since it last received a request. Call
super().perform_idle_actions() if you override. See the documentation for ``Server.main`` for full details on the
chain of ``Server`` method calls.

.. _pysoa.server.server.Server.perform_post_request_actions:

``method perform_post_request_actions()``
*****************************************

Runs just after the server processes a request. Call super().perform_post_request_actions() if you override. Be
sure your purpose for overriding isn't better met with middleware. See the documentation for ``Server.main`` for
full details on the chain of ``Server`` method calls.

.. _pysoa.server.server.Server.perform_pre_request_actions:

``method perform_pre_request_actions()``
****************************************

Runs just before the server accepts a new request. Call super().perform_pre_request_actions() if you override.
Be sure your purpose for overriding isn't better met with middleware. See the documentation for ``Server.main``
for full details on the chain of ``Server`` method calls.

.. _pysoa.server.server.Server.process_job:

``method process_job(job_request)``
***********************************

Validate, execute, and run the job request, wrapping it with any applicable job middleware.

Parameters
  - ``job_request`` (``dict``) - The job request

Returns
  ``JobResponse`` - A ``JobResponse`` object

Raises
  ``JobError``

.. _pysoa.server.server.Server.run:

``method run()``
****************

Starts the server run loop and returns after the server shuts down due to a shutdown-request, Harakiri signal,
or unhandled exception. See the documentation for ``Server.main`` for full details on the chain of ``Server``
method calls.

.. _pysoa.server.server.Server.setup:

``method setup()``
******************

Runs just before the server starts, if you need to do one-time loads or cache warming. Call super().setup() if
you override. See the documentation for ``Server.main`` for full details on the chain of ``Server`` method calls.


.. _pysoa.server.settings.PolymorphicServerSettings

``settings schema class PolymorphicServerSettings``
+++++++++++++++++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.server.settings``

Settings for Servers that can use any type of transport, while performing validation on certain transport types.

Settings Schema Definition
**************************

- ``client_routing`` - flexible ``dict``: Client settings for sending requests to other services; keys should be service names, and values should be the corresponding configuration dicts, which will be validated using the PolymorphicClientSettings schema

  keys
    ``unicode``: *(no description)*

  values
    flexible ``dict``: *(no description)*

    keys
      ``hashable``: *(no description)*

    values
      ``anything``: *(no description)*


- ``extra_fields_to_redact`` - ``set``: Use this field to supplement the set of fields that are automatically redacted/censored in request and response fields with additional fields that your service needs redacted.

  values
    ``unicode``: *(no description)*
- ``harakiri`` - strict ``dict``: Instructions for automatically terminating a server process when request processing takes longer than expected.

  - ``shutdown_grace`` - ``integer``: Seconds to forcefully shutdown after harakiri is triggered if shutdown does not occur (additional information: ``{u'gt': 0}``)
  - ``timeout`` - ``integer``: Seconds of inactivity before harakiri is triggered; 0 to disable, defaults to 300 (additional information: ``{u'gte': 0}``)

- ``heartbeat_file`` - ``unicode`` (nullable): If specified, the server will create a heartbeat file at the specified path on startup, update the timestamp in that file after the processing of every request or every time idle operations are processed, and delete the file when the server shuts down. The file name can optionally contain the specifier {{pid}}, which will be replaced with the server process PID.
- ``logging`` - strict ``dict``: Settings for service logging, which should follow the standard Python logging configuration

  - ``disable_existing_loggers`` - ``boolean``: *(no description)*
  - ``filters`` - flexible ``dict``: *(no description)*

    keys
      ``unicode``: *(no description)*

    values
      strict ``dict``: *(no description)*

      - ``()`` - ``anything``: The optional filter class
      - ``name`` - ``unicode``: The optional filter name

      Optional keys: ``()``, ``name``


  - ``formatters`` - flexible ``dict``: *(no description)*

    keys
      ``unicode``: *(no description)*

    values
      strict ``dict``: *(no description)*

      - ``datefmt`` - ``unicode``: *(no description)*
      - ``format`` - ``unicode``: *(no description)*

      Optional keys: ``datefmt``


  - ``handlers`` - flexible ``dict``: *(no description)*

    keys
      ``unicode``: *(no description)*

    values
      strict ``dict``: *(no description)*

      - ``class`` - ``unicode``: *(no description)*
      - ``filters`` - ``list``: *(no description)*

        values
          ``unicode``: *(no description)*
      - ``formatter`` - ``unicode``: *(no description)*
      - ``level`` - ``unicode``: *(no description)*

      Extra keys of any value are allowed. Optional keys: ``filters``, ``formatter``, ``level``


  - ``incremental`` - ``boolean``: *(no description)*
  - ``loggers`` - flexible ``dict``: *(no description)*

    keys
      ``unicode``: *(no description)*

    values
      strict ``dict``: *(no description)*

      - ``filters`` - ``list``: *(no description)*

        values
          ``unicode``: *(no description)*
      - ``handlers`` - ``list``: *(no description)*

        values
          ``unicode``: *(no description)*
      - ``level`` - ``unicode``: *(no description)*
      - ``propagate`` - ``boolean``: *(no description)*

      Optional keys: ``filters``, ``handlers``, ``level``, ``propagate``


  - ``root`` - strict ``dict``: *(no description)*

    - ``filters`` - ``list``: *(no description)*

      values
        ``unicode``: *(no description)*
    - ``handlers`` - ``list``: *(no description)*

      values
        ``unicode``: *(no description)*
    - ``level`` - ``unicode``: *(no description)*
    - ``propagate`` - ``boolean``: *(no description)*

    Optional keys: ``filters``, ``handlers``, ``level``, ``propagate``

  - ``version`` - ``integer``: *(no description)* (additional information: ``{u'gte': 1, u'lte': 1}``)

  Optional keys: ``filters``, ``formatters``, ``handlers``, ``incremental``, ``loggers``, ``root``, ``version``

- ``metrics`` - strict ``dict``: Configuration for defining a usage and performance metrics recorder

  - ``kwargs`` - strict ``dict``: The keyword arguments that will be passed to the constructed metrics recorder

    - ``config`` - flexible ``dict``: Whatever metrics configuration is required

      keys
        ``hashable``: *(no description)*

      values
        ``anything``: *(no description)*


    Extra keys of any value are allowed. Optional keys: ``config``

  - ``path`` - ``unicode``: The path to the class extending ``MetricsRecorder``, in the format ``module.name:ClassName``

  Optional keys: ``kwargs``

- ``middleware`` - ``list``: The list of all ``ServerMiddleware`` objects that should be applied to requests processed by this server

  values
    strict ``dict``: *(no description)*

    - ``kwargs`` - flexible ``dict``: Any keyword arguments that should be passed to the class when constructing a new instance

      keys
        ``unicode``: *(no description)*

      values
        ``anything``: *(no description)*

    - ``path`` - ``unicode``: The path to the class to be imported and used, in the format ``module.name:ClassName``

    Optional keys: ``kwargs``

- ``request_log_error_level`` - ``constant``: The logging level at which full request and response contents will be logged for requests whose responses contain errors (setting this to a more severe level than ``request_log_success_level`` will allow you to easily filter for unsuccessful requests) (additional information: ``{u'values': [u'DEBUG', u'INFO', u'WARNING', u'CRITICAL', u'ERROR']}``)
- ``request_log_success_level`` - ``constant``: The logging level at which full request and response contents will be logged for successful requests (additional information: ``{u'values': [u'DEBUG', u'INFO', u'WARNING', u'CRITICAL', u'ERROR']}``)
- ``transport`` - dictionary whose schema switches based on the value of ``path``, dynamically based on class imported from ``path`` (see the settings schema documentation for the class named at ``path``){}

Default Values
**************

Keys present in the dict below can be omitted from compliant settings dicts, in which case the values below will
apply as the default values.

.. code-block:: python

    {
        "client_routing": {},
        "extra_fields_to_redact": [],
        "harakiri": {
            "shutdown_grace": 30,
            "timeout": 300
        },
        "heartbeat_file": null,
        "logging": {
            "disable_existing_loggers": false,
            "filters": {
                "pysoa_logging_context_filter": {
                    "()": "pysoa.common.logging.PySOALogContextFilter"
                }
            },
            "formatters": {
                "console": {
                    "format": "%(asctime)s %(levelname)7s %(correlation_id)s %(request_id)s: %(message)s"
                },
                "syslog": {
                    "format": "%(service_name)s_service: %(name)s %(levelname)s %(module)s %(process)d correlation_id %(correlation_id)s request_id %(request_id)s %(message)s"
                }
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "filters": [
                        "pysoa_logging_context_filter"
                    ],
                    "formatter": "console",
                    "level": "INFO"
                },
                "syslog": {
                    "address": [
                        "localhost",
                        514
                    ],
                    "class": "pysoa.common.logging.SyslogHandler",
                    "facility": 23,
                    "filters": [
                        "pysoa_logging_context_filter"
                    ],
                    "formatter": "syslog",
                    "level": "INFO"
                }
            },
            "loggers": {},
            "root": {
                "handlers": [
                    "console"
                ],
                "level": "INFO"
            },
            "version": 1
        },
        "metrics": {
            "path": "pysoa.common.metrics:NoOpMetricsRecorder"
        },
        "middleware": [],
        "request_log_error_level": "INFO",
        "request_log_success_level": "INFO",
        "transport": {
            "path": "pysoa.common.transport.redis_gateway.server:RedisServerTransport"
        }
    }


.. _pysoa.server.standalone.simple_main:

``function simple_main(server_getter)``
++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.server.standalone``

Call this within ``__main__`` to start the service as a standalone server without Django support. Your server should
not have ``use_django=True``. If it does, see ``django_main``, instead.

Parameters
  - ``server_getter`` - A callable that returns the service's ``Server`` class (not an instance of it)


.. _pysoa.server.standalone.django_main:

``function django_main(server_getter)``
++++++++++++++++++++++++++++++++++++

**module:** ``pysoa.server.standalone``

Call this within ``__main__`` to start the service as a standalone server with Django support. Your server should have
``use_django=True``. If it does not, see ``simple_main``, instead.

Parameters
  - ``server_getter`` - A callable that returns the service's ``Server`` class (not an instance of it). Your service
    code should not be imported until the ``server_getter`` callable is called, otherwise Django
    errors will occur.


.. _pysoa.server.types.EnrichedActionRequest:

``class EnrichedActionRequest``
+++++++++++++++++++++++++++++++

**module:** ``pysoa.server.types``

- ``object``

  - `pysoa.common.types.ActionRequest`_

    - ``EnrichedActionRequest``

The action request object that the Server passes to each Action class that it calls. It contains all the information
from ActionRequest, plus some extra information from the JobRequest, a client that can be used to call other
services, and a helper for running asyncio coroutines.

Also contains a helper for easily calling other local service actions from within an action.

Services and intermediate libraries can subclass this class and change the ``Server`` attribute ``request_class`` to
their subclass in order to use more-advanced request classes. In order for any new attributes such a subclass
provides to be copied by ``call_local_action``, they must be ``attr.ib`` attributes with a default value.

.. _pysoa.server.types.EnrichedActionRequest-attrs-docs:

Attrs Properties
****************

- ``action`` (required)
- ``body``
- ``switches``
- ``context``
- ``control``
- ``client``
- ``async_event_loop``
- ``run_coroutine``

.. _pysoa.server.types.EnrichedActionRequest.call_local_action:

``method call_local_action(action, body, raise_action_errors=True)``
********************************************************************

This helper calls another action, locally, that resides on the same service, using the provided action name
and body. The called action will receive a copy of this request object with different action and body details.

The use of this helper differs significantly from using the PySOA client to call an action. Notably:

* The configured transport is not involved, so no socket activity or serialization/deserialization takes place.
* PySOA server metrics are not recorded and post-action cleanup activities do not occur.
* No "job request" is ever created or transacted.
* No middleware is executed around this action (though, in the future, we might change this decision and add
  middleware execution to this helper).

Parameters
  - ``action`` (``union[str, unicode]``) - The action to call (must exist within the ``action_class_map`` from the ``Server`` class)
  - ``body`` (``dict``) - The body to send to the action
  - ``raise_action_errors`` (``bool``) - If ``True`` (the default), all action errors will be raised; otherwise, an
    ``ActionResponse`` containing the errors will be returned.

Returns
  ``ActionResponse`` - the action response.

Raises
  ``ActionError``
