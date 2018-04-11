from __future__ import unicode_literals

from setuptools import setup, find_packages

from pysoa import __version__


def readme():
    with open('README.rst') as f:
        return f.read()


install_requires = [
    'enum34;python_version<"3.4"',
    'six~=1.10',
    'attrs~=17.4',
    'conformity~=1.9',
    'currint~=1.6',
    'redis~=2.10',
    'msgpack-python~=0.4',
]

tests_require = [
    'pytest',
    'pytest-cov',
    'mock>=2.0',
    'factory_boy~=2.8.0',
    'lunatic-python-universal~=2.1',
    'mockredispy~=2.9',
    'freezegun~=0.3',
]

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
    install_requires=install_requires,
    tests_require=tests_require,
    setup_requires=['pytest-runner'],
    test_suite='tests',
    extras_require={
        'testing': tests_require,
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
