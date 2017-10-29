pysoa
=====

A general-purpose library for writing Python (micro)services and their clients,
based on an RPC (remote procedure call) calling style. Provides both a client
and a server, which can be used directly by themselves or, as we do, extended with
extra functionality (our authentication, metrics and other code is all written
as middleware and run on top of this library).

The intended transport is an `ASGI <http://channels.readthedocs.io/en/latest/asgi.html>`_
channel layer, specifically the `asgi-redis <https://github.com/django/asgi_redis>`_
python package, which we use in combination with redis-sentinel in clusters. There is
also a local transport implementation for testing and other uses.

The basic tenets of the framework are:

* Services and actions both have simple names, and are called from the client by name.
  You can call actions individually, or bundle multiple action calls into a Job to
  be run serially (either aborting or continuing on error).

* Requests and responses are simply Python ``dicts``, using our validation framework
  `conformity <https://github.com/eventbrite/conformity>`_ in order to verify their
  schema on the way in and out.

* Message bodies are encoded using `MessagePack <http://msgpack.org/>`_, with
  a few non-standard types encoded using msgpack's ``ext``, such as datetimes and
  amounts of currency (using our `currint <https://github.com/eventbrite/currint>`_
  library)

* Requests have a ``context``, which is sourced from the original client context
  (web request, API request, etc.) and automatically chained down into client calls
  inside the service. This is used for things like correlation IDs, locales, etc.

* We include "SOA Switches" as a first-party implementation of feature flags/toggles.
  Like the context, they are bundled along with every request and automatically
  chained, and are packed to try and ensure they have minimal overhead.


Servers
-------

SOA servers run as standalone processes and connect out to their transport
to service requests and send responses, with no listening ports. This means they
can easily be scaled by simply launching or killing instances with whatever
orchestration software you want to use.

You can run all of the servers under a single channel layer (redis instance/
sentinel cluster), have a separate layer per service, or have separate layers
for different quality of service levels for your site based on the access point
and type of accessing user.

Servers declare one or more Actions, which are registered on the class. Actions
are a class that, once instatiated, gets called with a request and returns a
response; we provide a base Action class that extends this contract to also
implement validation on requests and responses, but there is no requirement to
use this if your requirements are more complex.

::

    from pysoa.server import Server as BaseServer
    class Server(BaseServer):

        service_name = 'example'

        action_class_map = {
            'square': SquareAction,
        }


Clients
-------

Clients are instantiated with a ClientRouter, which contains a dictionary of
service names and the transports by which they can be reached, and then has
two calling styles:

* Calling a single action and getting the response back directly using ``call_action``::

    result = client.call_action("square", {"number": 42})

* Creating a Job of multiple action requests, and sending it off to all be
  processed at once::

    results = client.call_actions([
        {"action": "square", "body": {"number": 42}},
        {"action": "power", "body": {"number": 212, "factor": 3}},
    ])


Middleware
----------

Both clients and servers can be extended using middleware, which in the Django
style, is code that wraps around a request-response call, either on the client
or server side, to add or mutate things in the request or response.

For example, some of our internal server middleware:

* Reads authentication tokens from the request and validates them to make sure
  the request is valid and not too old

* Logs metrics at the start and end of an action being processed so we can track
  how long our code is taking to run

* Catches errors in server code and logs it into Sentry so we can track and fix
  problems in production


Settings
--------

Both client and server also use a dict-based settings system, with a
`conformity <https://github.com/eventbrite/conformity>`_-defined schema to ensure
that whatever is passed in is valid (this is extensible by service implementations
if they have special settings they need set).

The server also has an integration mode with Django where it will read its
settings from ``django.conf.settings.SOA_SERVER_SETTINGS`` for both running and
for tests, which allows easy integration of Django models and application
logic into services (we make heavy use of the Django ORM).


Testing
-------

Services can be tested using standard unit tests and either by calling the
actions directly (after all, they are just callables), or if a run through the
server machinery is desired, using the ``ServerTestCase`` base class which takes
care of setting up local transports for you.

For entire-system integration tests, you will need to spin up a copy of each
desired service individually and point them at an integration-test-specific
channel layer to ensure isolation from the rest of the system.

There is also a StubClient available for testing code that calls services, but
where you do not actually want to have the service code in place.

For testing this library directly, you must first install Lua on your system
(on Mac OS X this is done with ``brew install lua``), ensure Lua is on your
``$PKG_CONFIG_PATH`` environment variable (in Mac OS X), and then install
dependencies (``pip install -e .[testing]``). After this, you can simply run
``pytest`` or ``setup.py test``.
