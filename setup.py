#!/usr/bin/env python

from setuptools import setup, find_packages

setup(name="eppicpipeline",
    #Pipeline version plus eppic version
    version="0.0.2.3.0.0",
    description="Tools for running EPPIC",
    url="http://github.com/eppic/eppic-pipeline",
    author="Spencer Bliven",
    author_email="eppic@systemsx.ch",
    license="GPL2",
    install_requires=[
        "luigi  >= 2.3",
        "pybars >= 0.0.4",
        "PyMySql >= 0.7.9", #some versions of luigi need mysql-connector-python-rf too.
        "subprocess32 >= 3.2",
    ],
    packages=find_packages(),
    package_data={'': ['*.hbs','*.list']}

    )
