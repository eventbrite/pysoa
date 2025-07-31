Contributing
============

Contributions are welcome, and they are greatly appreciated! Every little bit helps, and credit will always be given.

You can contribute in many ways:

Types of Contributions
----------------------

Report Bugs
~~~~~~~~~~~

Report bugs at https://github.com/eventbrite/pysoa/issues.

If you are reporting a bug, please include:

* Your operating system name and version.
* Your Python interpreter type and version.
* Any details about your local setup that might be helpful in troubleshooting.
* Detailed steps to reproduce the bug.

Fix Bugs
~~~~~~~~

Look through the GitHub issues for bugs. Anything tagged with "bug" is open to whoever wants to fix it.

Implement Features
~~~~~~~~~~~~~~~~~~

Look through the GitHub issues for features. Anything tagged with "feature" is open to whoever wants to implement it.

Write Documentation
~~~~~~~~~~~~~~~~~~~

PySOA could always use more documentation, whether as part of the official PySOA docs, in docstrings, or even on the
web in blog posts, articles, and more.

Submit Feedback
~~~~~~~~~~~~~~~

The best way to send feedback is to file an issue at https://github.com/eventbrite/pysoa/issues.

If you are proposing a feature:

* Explain in detail how it would work.
* Keep the scope as narrow as possible, to make it easier to implement.
* Remember that contributions are welcome. :)

Get Started
-----------

Ready to contribute? Here's how to set up PySOA for local development.

1. Ensure that Lua 5.2 or newer and its development headers are installed on your local system using one of the
   following techniques (or equivalent) based on your system. PySOA does not use Lua in your services, but PySOA's own
   tests use Lua when mocking Redis::

        $ brew install lua                          # macOS (see https://brew.sh/)
        $ apt-get install lua5.2 liblua5.2-dev      # Ubuntu
        $ yum install lua lua-devel                 # CentOS

2. Fork the ``pysoa`` repository on GitHub.
3. Clone your fork locally::

       $ git clone git@github.com:your_name_here/pysoa.git

4. Create a Python 3.12 virtualenv for installing PySOA dependencies::

       $ python3.12 -m venv venv
       $ source venv/bin/activate
       (venv) $ pip install --upgrade pip setuptools wheel
       (venv) $ pip install -e '.[testing]'

5. Make sure the tests pass on master before making any changes; otherwise, you might have an environment issue::

       (venv) $ ./test.sh

6. Create a branch for local development::

       $ git checkout -b name-of-your-bugfix-or-feature

   Now you can make your changes locally.

7. As you make changes, and when you are done making changes, regularly check that Flake8 and MyPy analysis and all of
   the tests pass. You should also include new tests or assertions to validate your new or changed code::

       # this command runs unit and integration tests, Flake8 analysis, and MyPy analysis
       (venv) $ ./test.sh

       # to run a subset of tests (either with PyTest directly or with ./test.sh, both shown here)
       (venv) $ pytest path/to/test/folder
       (venv) $ pytest path/to/test/module.py
       (venv) $ ./test.sh -k name_of_module.py
       (venv) $ ./test.sh -k NameOfTestClass
       (venv) $ ./test.sh -k name_of_test_function_or_method

       # to run functional tests (requires Docker >= 2.0.0 and Docker-Compose >= 1.23 [`pip install docker-compose`])
       # functional tests will actually spin up several different PySOA services and Redis Sentinel clusters and test
       # that everything works end-to-end.
       $ ./functional.sh

   You can also take advantage of the Tox setup to run all of the unit and integration tests locally in multiple
   environments using Docker::

       $ ./tox.sh

8. When you think you're ready to commit, run ``isort`` to organize your imports::

       $ isort

9. Commit your changes and push your branch to GitHub::

       $ git add -A
       $ git commit -m "[PATCH] Your detailed description of your changes"
       $ git push origin name-of-your-bugfix-or-feature

   Commit messages should start with ``[PATCH]`` for bug fixes that don't impact the *public* interface of the library,
   ``[MINOR]`` for changes that add new feature or alter the *public* interface of the library in non-breaking ways,
   or ``[MAJOR]`` for any changes that break backwards compatibility. This project strictly adheres to SemVer, so these
   commit prefixes help guide whether a patch, minor, or major release will be tagged. You should strive to avoid
   ``[MAJOR]`` changes, as they will not be released until the next major milestone, which could be as much as a year
   away.

10. Submit a pull request through the GitHub website.

Pull Request Guidelines
-----------------------

Before you submit a pull request, check that it meets these guidelines:

1. The pull request should include tests.
2. If the pull request adds functionality, the documentation should be updated. Put your new functionality into a
   class or function with a docstring, and add the feature to the appropriate location in ``docs/``. If you created a
   new module and it contains classes that should be publicly documented, add an autodoc config for that module to
   ``docs/reference.rst``.
3. The pull request should work for Python 3.12+. Make sure that the tests pass for all supported Python versions.
