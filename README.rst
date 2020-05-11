PySOA - Fast Python (micro)Services
===================================

.. image:: https://readthedocs.org/projects/pysoa/badge/
    :target: https://pysoa.readthedocs.io

.. image:: https://pepy.tech/badge/pysoa
    :target: https://pepy.tech/project/pysoa

.. image:: https://img.shields.io/pypi/l/pysoa.svg
    :target: https://pypi.python.org/pypi/pysoa

.. image:: https://api.travis-ci.org/eventbrite/pysoa.svg
    :target: https://travis-ci.org/eventbrite/pysoa

.. image:: https://img.shields.io/pypi/v/pysoa.svg
    :target: https://pypi.python.org/pypi/pysoa

.. image:: https://img.shields.io/pypi/wheel/pysoa.svg
    :target: https://pypi.python.org/pypi/pysoa

.. image:: https://img.shields.io/pypi/pyversions/pysoa.svg
    :target: https://pypi.python.org/pypi/pysoa


**PySOA** is a general-purpose library for writing fast Python (micro)services and their clients, based on an RPC
(remote procedure call) calling style. It provides both a client and a server, which can be used directly by themselves
or, as we do, extended with extra functionality (our authentication, database routing, and other code is written as
private middleware and runs on top of this library).

PySOA uses the concept of pluggable "transports" to define a layer for sending requests and responses (messages)
between clients and servers. The default, production-ready included transport is a `Redis <https://redis.io/>`_ pub-sub
layer, which we use in combination with Redis Sentinel in clusters. A single Redis cluster is capable of handling tens
of thousands of PySOA messages per second with extremely efficient and desirable load-balancing properties. There is
also a local transport implementation primarily used for testing and demonstration but capable of being used in
production where appropriate.


Basic Tenets
------------

- Services and actions both have simple names, and are called from the client by name. You can call actions
  individually, or bundle multiple action calls into a "job" to be run serially (either aborting or continuing on
  error).

- Requests and responses are simply Python dictionaries, and PySOA uses our open source validation framework
  `Conformity <https://github.com/eventbrite/conformity>`_ in order to verify their schema on the way in and out.

- Message bodies are encoded using `MessagePack <http://msgpack.org/>`_ by default (however, you can define your own
  serializer), with a few non-standard types encoded using MessagePack extensions, such as dates, times, date-times,
  and amounts of currency (using our open source `currint <https://github.com/eventbrite/currint>`_ library).

- Requests have a ``context``, which is sourced from the original client context (web request, API request, etc.) and
  automatically chained down into subsequent client calls made inside the service. This is used for contextual request
  information like correlation IDs, authentication tokens, locales, etc.

- We include "SOA Switches" as a first-party implementation of feature flags/toggles. Part of the context, they are
  bundled along with every request and automatically chained, and are packed as integers to ensure they have minimal
  overhead.

This intro summarizes some of the key concepts of using PySOA. For more thorough documentation, see the
`PySOA Documentation <https://pysoa.readthedocs.io>`_.


License
-------

PySOA is licensed under the `Apache License, version 2.0 <LICENSE>`_.


Installation
------------

PySOA is available in PyPi and can be installing directly via Pip or listed in ``setup.py``, ``requirements.txt``,
or ``Pipfile``:

.. code-block:: bash

    pip install 'pysoa~=1.2'

.. code-block:: python

    install_requires=[
        ...
        'pysoa~=1.2',
        ...
    ]

.. code-block:: text

    pysoa~=1.2

.. code-block:: text

    pysoa = {version="~=1.2"}


Documentation
-------------

The complete PySOA documentation is available on `Read the Docs <https://pysoa.readthedocs.io>`_!
