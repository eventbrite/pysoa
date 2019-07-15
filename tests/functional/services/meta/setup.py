from setuptools import setup

from meta_service.version import __version__


setup(
    name='meta_service',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='A small service for running functional tests in PySOA',
    url='http://github.com/eventbrite/pysoa',
    packages=['meta_service'],
    entry_points={
        'console_scripts': [
            'meta_service=meta_service.standalone:main',
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
