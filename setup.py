from setuptools import setup
import os


__version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'pysoa',
                                   'version.txt'
                                   )
__version__ = open(__version_file_path).read()  # noqa

setup(
    name='pysoa',
    version=__version__,
    packages=['pysoa'],
    include_package_data=True,
    install_requires=[
        'conformity',
        'msgpack-python>=0.4',
        'six>=1.10',
        'attrs>=16.3',
    ],
    dependency_links=[
        'git+ssh://git@github.com/eventbrite/conformity.git@1.2.0#egg=conformity-1.2.0',
    ],
    tests_require=[
        'mock>=2.0',
    ],
    test_suite='tests',
)
