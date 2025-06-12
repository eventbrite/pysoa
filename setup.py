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
    'attrs>=18.2,<23',
    'conformity~=1.28',
    'currint>=1.6,<3',
    'msgpack~=0.6,>=0.6.2',
    'pymetrics~=1.0.7',
    'pytz>=2019.1',
    'redis>=2.10,<4.0,!=3.0.*,!=3.1.*,!=3.2.*,!=3.3.*',  # shortest way to say 2.10+ or 3.4+ but not older versions
    'six~=1.10',
]

test_helper_requirements = []

test_plan_requirements = test_helper_requirements + [
    'pyparsing~=2.2',
    'pytest>4.2,<8.0',
    'pytest-asyncio~=0.23.0',
    'Faker~=20.0.0'
]

mypy_require = [
    'mypy~=1.8.0',
    'types-six~=0.1.7',
    'types-setuptools~=57.0.0',
    'types-mock~=0.1.3',
    'types-requests~=2.25.6',
    'types-pytz',
    'types-redis',
    'typing-extensions~=4.9.0',
]

# testing
tests_require = [
    'coverage~=7.4.0',
    'factory_boy~=3.3.0',
    'freezegun~=1.4.0',
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
            'sphinx~=7.0.0',
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
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
        'Topic :: Software Development',
    ],
    project_urls={
        'Documentation': 'https://pysoa.readthedocs.io',
        'Issues': 'https://github.com/eventbrite/pysoa/issues',
        'CI': 'https://travis-ci.org/eventbrite/pysoa/',
    },
)
