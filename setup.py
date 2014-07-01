#!/usr/bin/python
import os
from setuptools import setup

this_dir = os.path.realpath(os.path.dirname(__file__))
long_description = open(os.path.join(this_dir, 'README.md'), 'r').read()

setup(
    name = 'halo',
    version = '0.1',
    author = 'Kenji Wellman',
    author_email = 'kenji.wellman@gmail.com',
    description = 'Framework for building mobile and web backends with a lot of common functionality built-in',
    license = 'BSD',
    packages = ['halo'],
    long_description = long_description,
    install_requires=['Flask', 'flask-peewee'],
)
