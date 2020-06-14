#!/usr/bin/env python

from setuptools import setup


setup(
    name='indigo-backfill-influx',
    author='daveb@smurfless.com',
    url='',
    versioning='dev',
    setup_requires=['setupmeta'],
    dependency_links=['https://pypi.org/project/setupmeta'],
    include_package_data=True,
    python_requires='>=3.7',
    install_requires=[
        'betterproto',
        'click',
        'influxdb-client',
    ],
    extras_require={
        'dev': [
            'behave',
            'betterproto[compiler]',
            'flake8',
            'invoke',
            'tox',
            'mypy',
            'pytest'
        ]
    },
    entry_points={
        'console_scripts': ['indigo-backfill-influx=backfill:main'],
    }
)
