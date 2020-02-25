PySOA Release Roadmap
=====================

PySOA is an Open Source project and, as such, it is subject to the changing tides of technology and the marketplace of
Open Source Software. This means that no guarantee or warranty is made as to the support or lifetime of PySOA. It may
be supported for many years to come, or it may not. Of course, the community is always free to fork this project to
alter its direction or extend its life should support come to an end.

With that said, the below roadmap represents the planned support for PySOA versions as of 2019-December-01. It is
subject to change at any time, but probably won't change significantly.

.. contents:: Contents
    :local:
    :depth: 3
    :backlinks: none


General Versioning and Support Strategy
+++++++++++++++++++++++++++++++++++++++

* There will be a new major version of PySOA approximately every one year (twelve Gregorian months), and between those
  major versions will generally be three, but possibly more, minor versions. Patch versions will be released as needed.
  We strictly follow `SemVer <https://semver.org/>`_, so breaking changes will be made only in major versions and, were
  possible, will be preceded by deprecation warnings added in minor versions.
* For any given supported minor version, only the latest patch version is supported; older patch versions are not. So,
  for example, if PySOA 1.1.x is supported and 1.1.2 is released, then only 1.1.2 is supported; 1.1.0 and 1.1.1 are
  not.
* The last minor version in a major series is considered Long Term Support (LTS) and is supported until the release of
  the major version following the subsequent major version. So, for example, if 1.3 is the last minor version of 1.x,
  it will be supported until 3.0.0 is released. All intermediary minor versions are supported until two minor versions
  following. So, for example, PySOA 1.0.x will be supported until PySOA 1.2.x is released, and PySOA 1.1.x until PySOA
  1.3.x is released, etc.
* ``[PATCH]`` commits that are bug fixes are applied to all currently-supported branches affected by the associated
  bug.


Planned Major/Breaking Changes
++++++++++++++++++++++++++++++

* 2.0.0 will support Python 3.7+ only. It will not support Python 2.x or Python 3 versions older than 3.7.x.
* 2.0.0 will support Django 2.2+ only. It will not support Django 1.x or Django 2 versions older than 2.2.x.
* 2.0.0 will require Conformity 2.x, Attrs 20.x+, Currint 3.x, PyMetrics 2.x, and Redis (the server, not the library)
  5+.


Planned Roadmap
+++++++++++++++

The following table shows the current planned roadmap for release dates and support dates.

+--------------+-----------------+-------------------+-------------------+---------------------+
| Release      | Supported Patch | Release Date      | Support Ends With | End of Support Date |
+==============+=================+===================+===================+=====================+
| < 0.74.0     | n/a             | n/a               | 1.0.0             | 2019-12-02          |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 0.74.x       | 0.74.0          | 2019-11-05        | 1.1.0             | 2020-01-27          |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 1.0.x        | 1.0.4           | 2019-12-02        | 1.2.0             | 2020-05-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 1.1.x        | 1.1.3           | 2020-01-27        | 1.3.0             | 2020-08-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 1.2.x        | n/a             | 2020-05-01 [#f2]_ | 2.0.0             | 2020-11-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 1.3.x [#f1]_ | n/a             | 2020-08-01 [#f2]_ | 3.0.0             | 2021-11-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 2.0.x        | n/a             | 2020-11-01        | 2.2.0             | 2021-05-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 2.1.x        | n/a             | 2021-02-01 [#f2]_ | 2.3.0             | 2021-08-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 2.2.x        | n/a             | 2021-05-01 [#f2]_ | 3.0.0             | 2021-11-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 2.3.x [#f1]_ | n/a             | 2021-08-01 [#f2]_ | 4.0.0             | 2022-11-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+
| 3.0.x        | n/a             | 2021-11-01        | 3.2.0             | 2022-05-01 [#f2]_   |
+--------------+-----------------+-------------------+-------------------+---------------------+

.. rubric:: Footnotes
.. [#f1] Long Term Support (LTS)
.. [#f2] Planned date (has not yet occurred, subject to change)
