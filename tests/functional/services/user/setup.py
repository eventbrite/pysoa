from setuptools import setup

from user_service.version import __version__


setup(
    name='user_service',
    version=__version__,
    author='Eventbrite, Inc.',
    author_email='opensource@eventbrite.com',
    description='A small service for running functional tests in PySOA',
    url='http://github.com/eventbrite/pysoa',
    packages=['user_service'],
    install_requires=['sqlparse~=0.2.4', 'django~=2.2.0', 'mysqlclient~=1.3.14'],
    entry_points={
        'console_scripts': [
            'user_service=user_service.standalone:main',
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
