from setuptools import setup

# Load version information
execfile('server/version.py')

setup(
    name='pysoa-server',
    version=__version__,
    description='SOA Server reference Python implementation',
    packages=['server'],
    install_requires=[
        'msgpack-python>=0.4',
        'six>=1.10',
    ],
    tests_require=[
        'mock>=2.0',
    ],
    test_suite='tests',
)
