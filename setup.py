from __future__ import unicode_literals

from setuptools import setup, find_packages

from pysoa import __version__


def readme():
    with open('README.rst') as f:
        return f.read()


base_requirements = [
    'attrs~=17.4',
    'conformity~=1.12',
    'currint~=1.6',
    'enum34;python_version<"3.4"',
    'msgpack-python~=0.4',
    'redis~=2.10',
    'six~=1.10',
]

test_helper_requirements = [
    'mock>=2.0;python_version<"3.3"',
]

test_plan_requirements = test_helper_requirements + [
    'pyparsing~=2.2',
    'pytest~=3.1',
    'pytz>=2018.4',
]

test_requirements = [
    'factory_boy~=2.8.0',
    'freezegun~=0.3',
    'lunatic-python-universal~=2.1',
    'mockredispy~=2.9',
    'pytest-cov~=2.5',
] + test_plan_requirements

setup(
    name='pysoa',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='A Python library for writing (micro)services and their clients',
    long_description=readme(),
    url='http://github.com/eventbrite/pysoa',
    packages=list(map(str, find_packages(exclude=['*.tests', '*.tests.*', 'tests.*', 'tests']))),
    include_package_data=True,
    install_requires=base_requirements,
    tests_require=test_requirements,
    setup_requires=['pytest-runner'],
    test_suite='tests',
    extras_require={
        'testing': test_requirements,
        'test_helpers': test_helper_requirements,
        'test_plans': test_plan_requirements,
    },
    entry_points={
        'pytest11': [
            'pysoa_test_plan=pysoa.test.plugins.pytest',
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
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Topic :: Software Development',
    ],
)
