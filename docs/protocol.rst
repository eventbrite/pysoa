The PySOA Protocol
==================

While PySOA was written for a Python environment, there's no reason it has to be restricted to that. Both the source
code and the protocol are open and free, and the protocol is compatible with any platform. With the proper tools,
you could implement the PySOA protocol with Java, PHP, Perl, or even JavaScript (and, indeed, there is already a
`Javascript client for Node.JS <https://github.com/eventbrite/pysoa-node>`_). This document describes the PySOA
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
            [optional: "caller": <unicode>,]
            [optional: "calling_service": <unicode>,]
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

You can learn more about these objects and their contents in the reference documentation for dataclasses
:class:`pysoa.common.types.JobRequest` and :class:`pysoa.common.types.ActionRequest` and Conformity schema
`pysoa.server.schemas.JobResponseSchema <reference.html#module-pysoa.server.schemas>`_, respectively.

The PySOA Response Format
*************************

A PySOA response message is called a Job Response. Job Responses take the following format::

    {
        "actions": <list<Action Response>>,
        "context": {
            <optional service-defined keys and values,>
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
        "is_caller_error": <boolean: default false>,
        "message": <unicode>,
        [optional: "traceback": <unicode>,]
        [optional: "variables": <dictionary<unicode, unicode>>,]
    }

You can learn more about these objects and their contents in the reference documentation for dataclasses
:class:`pysoa.common.types.JobResponse`, :class:`pysoa.common.types.ActionResponse`, and
:class:`pysoa.common.errors.Error`, respectively.

Serialization Protocol
++++++++++++++++++++++

Before being transmitted between client and server, outgoing PySOA messages must be serialized and incoming PySOA
messages must be deserialized. There is actually no hard requirement on what serialization protocol you use: As long
as your clients speak the same serialization protocol as the services they call, they will be compatible. The reference
Python implementation of PySOA provides MessagePack and JSON serialization protocols. For more information about these,
see `Serialization <api.rst#serialization>`_. If you wish to communicate with clients or servers using these, you
must implement a compatible protocol. Some transports are capable of negotiating an acceptable serialization protocol,
while others will require pre-agreement. The Local Transport (where requests are handled in-memory within the same
Python process) is the only transport that performs no serialization.

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
requests and responses each second. In our production environment, 225 PySOA workers performing CPU-intensive tasks
(about half cryptography and set calculations and half blocking I/O against a MySQL database) handle approximately
10,000 requests per second. This load is spread across four Redis masters also used by dozens of other services with a
total of thousands of workers. These four Redis servers handle approximately 30,000 requests per second with about 30%
Redis CPU utilization.

The Redis Gateway Transport protocol is a versioned protocol that has different available features for each version.
Version 1, the first version, had no extra features other than the capability of sending a serialized envelope of
pre-agreed-upon content type. Version 2 added support for a content type header. Version 3 added a proper version
preamble and support for multiple headers.

The process begins when a client sends a message to a server in the following format, dependent on version:

Protocol Version 1 (no preambles or headers supported; content type is determined by agreeing client and server
configurations)::

    <serialized envelope>

Protocol Version 2 (content type header is not optional)::

    content-type:mime/type;<serialized envelope>

Protocol Version 3 (multiple headers supported, all headers optional/conditional)::

    pysoa-redis/3//[header-name:header-value;[...]]<serialized envelope>

    supported request headers (all optional/conditional):
        content-type : [application/msgpack], [application/json], [...]

The content should be a valid MIME type that both the client and server understand. The serializers shipped with PySOA
understand ``application/json`` and ``application/msgpack``, but defining a new ``Serializer`` class registers its
MIME type, so you can support whatever serialization technique you desire.

The "envelope," serialized in the specified MIME type, is a dictionary that contains and carries the ``JobRequest``
dictionary in the following format::

    {
        "body": <JobRequest dict>,
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

      pysoa:<service name>.<client instance UUID>!

* ``__expiry__``: The Unix-epoch timestamp in seconds (and fractional seconds after the decimal point) after which the
  request should be considered expired and discarded without the server handling it.

The client serializes the envelope as described above and sends it to Redis using this pseudocode::

    if(redis(`LLEN $server_key`) >= QUEUE_SIZE_LIMIT) {
        raise QueueFull
    }

    redis(`RPUSH $server_key $message`)
    redis(`EXPIRE $server_key $expiry`)

* ``$server_key``: A server-unique Redis ``LIST`` key name on which the server is blocked waiting for incoming
  requests. There are no hard rules about the naming convention this must follow unless either the client or server is
  using this reference implementation, in which case the key name must be in the following format::

      pysoa:<service name>

* ``$message``: The message containing the content type and serialized envelope as described above.
* ``$expiry``: An integer greater than or equal to the number of seconds between "now" and the meta field
  ``__expiry__``.

While this is going on, multiple server processes are blocked waiting for incoming requests on the agreed-upon service
``LIST`` key name::

    redis(`BLPOP $server_key`)

Once a server receives a message from Redis, it extracts the content-type, deserializes the envelope, verifies the
envelope is not expired, and returns the ``JobRequest`` dictionary to the server code for handling. If and when the
server is ready to send a response, the response is sent back to the client in a similar way that the client sent the
request:

Protocol Version 1::

    <serialized envelope>

Protocol Version 2::

    content-type:mime/type;<serialized envelope>

Protocol Version 3::

    pysoa-redis/3//[header-name:header-value;[...]]<serialized envelope or partial envelope>

    supported response headers (all optional/conditional):
        content-type : [application/msgpack], [application/json], [...]
        chunk-count : [1-9]+[0-9]*
        chunk-id : [1-9]+[0-9]*

The key difference between request and response messages begins in Protocol Version 3, where responses can now be
chunked. Response chunking, which is disabled by default, has to be enabled in the server transport configuration. Even
if enabled, the server will only chunk a response if it exceeds the configured threshold and the request includes a
version preamble indicating support for Version 3 or higher (meaning the client can understand the chunked response).

In a chunked response, chunks may but are not required to have a ``content-type`` header, and if multiple chunks have
the header, only the first chunk's ``content-type`` header is considered. Every chunk must have both the
``chunk-count`` header and the ``chunk-id`` header. The ``chunk-count`` header must be the same for all chunks, and the
``chunk-id`` header must start with ``1`` on the first chunk and increment until all chunks have been submitted. For
example, a chunked response may look like this::

    pysoa-redis/3//content-type:application/msgpack;chunk-count:5;chunk-id:1;<start of serialized envelope>
    pysoa-redis/3//chunk-count:5;chunk-id:2;<middle of serialized envelope>
    pysoa-redis/3//chunk-count:5;chunk-id:3;<middle of serialized envelope>
    pysoa-redis/3//chunk-count:5;chunk-id:4;<middle of serialized envelope>
    pysoa-redis/3//chunk-count:5;chunk-id:5;<end of serialized envelope>

The serialized envelope pieces from each chunk will be reassembled in order and then deserialized. (Note: Due to the
nature of the Redis transport and distributed workers, only responses can be chunked. Requests cannot be chunked, and
it is not even possible to configure chunking in the client transport.)

The response envelope is very similar to the request envelope::

    {
        "body": <JobResponse dict>,
        "meta": {
            "__expiry__": <float>,
        },
        "request_id": <integer>,
    }

And it is sent using the same Redis commands::

    if(redis(`LLEN $client_key`) >= QUEUE_SIZE_LIMIT) {
        raise QueueFull
    }

    redis(`RPUSH $client_key $message`)
    redis(`EXPIRE $client_key $expiry`)

* ``$client_key``: The key obtained from the ``reply_to`` meta field in the request envelope.

Meanwhile, the client has been blocked waiting for a response on the agreed-upon client ``LIST`` key name in the same
manner that the server waited for a request::

    redis(`BLPOP $client_key`)

Once the server sends the response, it can immediately start waiting for the next request on ``$server_key``. It does
not have to wait on the client to retrieve the response from Redis. When the client retrieves the response, it
deserializes the envelope and returns the ``JobResponse`` dictionary back to the client code for handling.
