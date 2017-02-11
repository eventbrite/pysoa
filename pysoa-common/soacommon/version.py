import os

version_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'version.txt')

with open(version_file_path) as version_file:
    __version__ = version_file.read()
__version_info__ = map(int, __version__.split('.', 2))

__all__ = ['__version__', '__version_info__']
