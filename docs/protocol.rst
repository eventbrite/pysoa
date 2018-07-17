The PySOA Protocol
==================

While PySOA was written for a Python environment, there's no reason it has to be restricted to that. Both the source
code and the protocol are open and free, and the protocol is compatible with any platform. With the proper tools,
you could implement the PySOA protocol with Java, PHP, Perl, or even JavaScript. This document describes the PySOA
protocol in detail.

PySOA actually has three, independent protocols. This document is divided into sections for each protocol and makes use
of pseudocode, JSON, and pseudo-JSON to demonstrate details in platform-independent ways.

.. contents:: Contents
    :local:
    :depth: 3
    :backlinks: none


PySOA Message Protocol
++++++++++++++++++++++

In PySOA, requests and responses are encapsulated in messages. Messages are a way for servers and clients to
communicate independent of the serialization protocol or transport protocol in use. Every request and every response
is a dictionary or mapping (terminology varies across platforms) with Unicode string keys (all dictionaries in
PySOA messages must have Unicode string keys). If your service or client written in a language other than Python
implements the following message formats, it will be able to communicate with any other PySOA service or client.

The PySOA Request Format
************************

A PySOA request message is called a Job Request. Job Requests take the following format::

    {
        "actions": <list<Action Request>>,
        "context": {
            "correlation_id": <unicode>,
            "request_id": <integer>,
            "switches": <list<integer>>,
            <optional service-defined keys,>
        },
        "control": {
            [optional: "continue_on_error": <boolean: default false>,]
            [optional: "suppress_response": <boolean: default false>,]
        },
    }

Action Requests take the following format::

    {
        "action": <unicode>,
        "body": {
            <optional service-defined keys,>
        },
    }

Some of these items require explanation:

* Correlation IDs can be used at your own discretion, but are generally shared across multiple service requests, even
  across multiple services, to correlate requests that are logically linked together (example: such as all PySOA
  requests that occur within the scope of a single HTTP request in a client application).
* Request ID: An ID unique to the client instance.
* Switches: See `Versioning using switches <api.rst#versioning-using-switches>`_.
* ``continue_on_error``: A control header indicating whether subsequent Action Requests should continue being processed
  even if previous Action Requests in the same Job Request encountered errors.
* ``suppress_response``: A control header indicating whether the client has invoked send-and-forget and does not
  require the server to send a response.

The PySOA Response Format
*************************

A PySOA response message is called a Job Response. Job Responses take the following format::

    {
        "actions": <list<Action Response>>,
        "context": {
            <optional service-defined keys,>
        },
        "errors": <list<Error>>,
    }

Action Responses take the following format::

    {
        "action": <unicode>,
        "body": {
            <optional service-defined keys,>
        },
        "errors": <list<Error>>,
    }

Errors take the following format::

    {
        "code": <unicode>,
        [optional: "denied_permissions": <list<unicode>>,]
        [optional: "field": <unicode>,]
        "message": <unicode>,
        [optional: "traceback": <unicode>,]
        [optional: "variables": <dictionary<unicode, unicode>>,]
    }

Serialization Protocol
++++++++++++++++++++++

Before being transmitted between client and server, outgoing PySOA messages must be serialized and incoming PySOA
messages must be deserialized. There is actually no hard requirement on what serialization protocol you use: As long
as your clients speak the same serialization protocol as the services they call, they will be compatible. The reference
Python implementation of PySOA provides MessagePack and JSON serialization protocols. For more information about these,
see `Serialization <api.rst#serialization>`_. If you wish to communicate with clients or servers using these, you
must implement a compatible protocol.

Transport Protocol
++++++++++++++++++

Like serialization, there is no hard requirement on what transport protocols you use: As long as your client implements
the transport protocol expected by the server, the two can communicate. The reference Python implementation of PySOA
provides two transports at this time. The Local Transport can only be used with Python servers and clients running in
the same process, so it is not relevant to non-Python implementations and will not be covered here. Other transports
may be supported in the future.

Redis Gateway Transport
***********************

The Redis Gateway Transport is a production-tested, performance-proven protocol that is compatible with any platform
for which there is a Redis client library. A beefy Redis server is capable of handling tens of thousands of PySOA
requests and responses each second. The process begins when a client sends a serialized PySOA message in an envelope
with the following format::

    {
        "body": <Job Request>,
        "meta": {
            "reply_to": <unicode>,
            "__expiry__": <float>,
        },
        "request_id": <integer>,
    }

* ``reply_to``: A client-unique Redis ``LIST`` key name to which the server should send its response and on which the
  client will block waiting for a response. There are no hard rules about the naming convention this must follow
  unless either the client or server is using this reference implementation, in which case the key name must be in the
  following format::

      pysoa:[service name].[client instance UUID]!

* ``__expiry__``: The Unix-epoch timestamp in seconds (and fractional seconds after the decimal point) after which the
  request should be considered expired and discarded without the server handling it.

The client serializes this envelope and sends it to Redis::

    if(redis(`LLEN $server_key`) >= QUEUE_SIZE_LIMIT) {
        raise QueueFull
    }

    redis(`RPUSH $server_key $serialized_envelope`)
    redis(`EXPIRE $server_key $expiry`)

* ``$server_key``: A server-unique Redis ``LIST`` key name on which the server is blocked waiting for incoming
  requests. There are no hard rules about the naming convention this must follow unless either the client or server is
  using this reference implementation, in which case the key name must be in the following format::

      pysoa:[service name]

* ``$serialized_envelope``: The serialized envelope.
* ``$expiry``: An integer greater than or equal to the number of seconds between "now" and the meta field
  ``__expiry__``.

While this is going on, multiple server processes are blocked waiting for incoming requests on the agreed-upon service
``LIST`` key name::

    redis(`BLPOP $server_key`)

Once a server receives an envelope from Redis, it verifies the envelope is not expired and returns the Job Request
to the server process for processing. If and when the server is ready to send a response, the response is sent back
to the client in a very similar way::

    {
        "body": <Job Response>,
        "meta": {
            "__expiry__": <float>,
        },
        "request_id": <integer>,
    }

Using the same Redis commands::

    if(redis(`LLEN $client_key`) >= QUEUE_SIZE_LIMIT) {
        raise QueueFull
    }

    redis(`RPUSH $client_key $serialized_envelope`)
    redis(`EXPIRE $client_key $expiry`)

* ``$client_key``: The key obtained from the ``reply_to`` meta field in the request envelope.

Meanwhile, the client has been blocked waiting for a response on the agreed-upon client ``LIST`` key name in the same
manner that the server waiting for a request::

    redis(`BLPOP $client_key`)
