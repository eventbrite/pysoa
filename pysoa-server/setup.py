from setuptools import setup
import os

# Load version information
__version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'soaserver',
                                   'version.txt')
__version__ = open(__version_file_path).read()  # noqa

setup(
    name='pysoa-server',
    version=__version__,
    description='SOA Server reference Python implementation',
    packages=['soaserver'],
    install_requires=[
        'msgpack-python>=0.4',
        'six>=1.10',
    ],
    tests_require=[
        'mock>=2.0',
    ],
    test_suite='tests',
)
