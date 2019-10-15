from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs

from setuptools import (
    find_packages,
    setup,
)

from pysoa import __version__


def readme():
    with codecs.open('README.rst', 'rb', encoding='utf8') as f:
        return f.read()


install_requires = [
    'attrs>=17.4,<20',
    'conformity~=1.26',
    'currint>=1.6,<3',
    'enum34;python_version<"3.4"',
    'msgpack-python~=0.5,>=0.5.2',
    'pymetrics~=0.21',
    'pytz>=2019.1',
    'redis~=2.10',
    'six~=1.10',
    'typing~=3.7.4;python_version<"3.5"',
    'typing-extensions~=3.7.4;python_version<"3.8"',

    # For context, see the comment in pysoa.common.compatibility. Due to the peculiarities of the patching detailed
    # there, we pin these dependencies to hard versions, or else things might break when they update. When new versions
    # come out, we'll bump and adjust our patching or, hopefully, relax and remove our patching.
    'contextvars==2.4;python_version>"3.4" and python_version<"3.7"',
    'aiocontextvars==0.2.2;python_version>"3.4" and python_version<"3.7"',
]

test_helper_requirements = [
    'mock>=2.0;python_version<"3.3"',
]

test_plan_requirements = test_helper_requirements + [
    'pyparsing~=2.2',
    'pytest>=3.1,<6,!=4.2.0',  # 4.2.0 has a regression breaking our test plans, fixed in 4.2.1
    'pytest-asyncio;python_version>"3.4"',
]

tests_require = [
    'coverage~=4.5',
    'factory_boy~=2.11.1',
    'freezegun~=0.3',
    'lunatic-python-universal~=2.1',
    'mockredispy~=2.9',
    'mypy~=0.730;python_version>"3.4"',
    'pytest-runner',
] + test_plan_requirements


setup(
    name='pysoa',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='A Python library for writing (micro)services and their clients',
    long_description=readme(),
    url='http://github.com/eventbrite/pysoa',
    packages=list(map(str, find_packages(include=['pysoa', 'pysoa.*']))),
    package_data={
        str('pysoa'): [str('py.typed')],  # PEP 561,
    },
    zip_safe=False,  # PEP 561
    include_package_data=True,
    install_requires=install_requires,
    tests_require=tests_require,
    test_suite='tests',
    extras_require={
        'testing': tests_require,
        'test_helpers': test_helper_requirements,
        'test_plans': test_plan_requirements,
    },
    entry_points={
        'pytest11': [
            'pysoa_test_plan=pysoa.test.plugins.pytest.plans',
            'pysoa_test_fixtures=pysoa.test.plugins.pytest.fixtures',
        ]
    },
    license='Apache 2.0',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Topic :: Software Development',
    ],
    project_urls={
        'Documentation': 'https://pysoa.readthedocs.io',
        'Issues': 'https://github.com/eventbrite/pysoa/issues',
        'CI': 'https://travis-ci.org/eventbrite/pysoa/',
    },
)
