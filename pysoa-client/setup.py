from setuptools import setup
import os


__version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   'soaclient',
                                   'version.txt')
__version__ = open(__version_file_path).read()  # noqa

setup(
    name='pysoa-client',
    version=__version__,
    packages=['soaclient'],
    include_package_data=True,
    install_requires=[],
    tests_require=[],
)
