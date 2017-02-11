from setuptools import setup
import os


__version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'soacommon',
                                   'version.txt')
__version__ = open(__version_file_path).read()  # noqa

setup(
    name='pysoa-common',
    version=__version__,
    packages=['soacommon'],
    include_package_data=True,
    install_requires=[],
    tests_require=[],
)
