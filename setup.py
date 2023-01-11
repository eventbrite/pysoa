from __future__ import (
    absolute_import,
    unicode_literals,
)

import codecs
import sys

from setuptools import (
    find_packages,
    setup,
)

from pysoa import __version__


def readme():
    with codecs.open('README.rst', 'rb', encoding='utf8') as f:
        return f.read()


install_requires = [
    'attrs>=18.2,<22',
    'conformity~=1.28',
    'currint>=1.6,<3',
    'enum34;python_version<"3.4"',
    'msgpack~=0.6,>=0.6.2',
    'pymetrics~=1.0.7',
    'pytz>=2019.1',
    'redis>=2.10,<4.0,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*',  # shortest way to say 2.10+ or 3.4+ but not older versions
    'six~=1.10',
    'typing~=3.7.4;python_version<"3.5"',
    'typing-extensions~=3.7.4;python_version<"3.7"',
    'typing-extensions~=3.10;python_version>="3.7"',

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
    'pytest>4.2,<5.4',
    'pytest-asyncio~=0.10.0;python_version>"3.4"',
    'Faker~=5.0.0;python_version>"3.4"'
]

mypy_require = [
    'mypy~=0.740,<=0.910;python_version>"3.4" and python_version<"3.7"',
    'mypy~=0.991;python_version>="3.7"',
    'types-six~=0.1.7;python_version>"3.4"',
    'types-setuptools~=57.0.0;python_version>"3.4"',
    'types-mock~=0.1.3;python_version>"3.4"',
    'types-requests~=2.25.6;python_version>"3.4"',
    'types-pytz;python_version>"3.6"',
    'types-redis;python_version>"3.6"',
]

# testing
tests_require = [
    'coverage~=4.5',
    'factory_boy~=2.11.1',
    'freezegun~=0.3',
    'lunatic-python-universal~=2.1',
    'mockredispy~=2.9',
    'parameterized~=0.7',
] + mypy_require + test_plan_requirements


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
    setup_requires=['pytest-runner'] if {'pytest', 'test', 'ptr'}.intersection(sys.argv) else [],
    test_suite='tests',
    extras_require={
        'docs': [
            'conformity[docs]~=1.26,>=1.26.4',
            'django~=1.11',
            'sphinx~=2.2;python_version>="3.6"',
        ] + test_plan_requirements,
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
        'Development Status :: 5 - Production/Stable',
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
        'Programming Language :: Python :: 3.8',
        'Topic :: Software Development',
    ],
    project_urls={
        'Documentation': 'https://pysoa.readthedocs.io',
        'Issues': 'https://github.com/eventbrite/pysoa/issues',
        'CI': 'https://travis-ci.org/eventbrite/pysoa/',
    },
)
