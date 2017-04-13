from setuptools import setup, find_packages
from pysoa import __version__


install_requires = [
    'conformity~=1.3',
    'msgpack-python>=0.4.8',
    'six>=1.10',
    'attrs>=16.3',
    'asgi_redis',
]

tests_require = [
    'pytest',
    'mock>=2.0',
    'factory_boy~=2.8.0',
]

setup(
    name='pysoa',
    version=__version__,
    packages=find_packages(exclude=["*.tests", "*.tests.*", "tests.*", "tests"]),
    include_package_data=True,
    install_requires=install_requires,
    tests_require=tests_require,
    setup_requires=['pytest-runner'],
    test_suite='tests',
    extras_require={
        'testing': tests_require,
    },
)
