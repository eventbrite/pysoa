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
    packages=['pysoa.client', 'pysoa.server', 'pysoa.common'],
    include_package_data=True,
    install_requires=[],
    tests_require=[],
)
