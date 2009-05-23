#!/usr/bin/env python

# Copyright (C) 2009 PyG3T development team
# Please see the accompanying LICENSE file for further information.

from distutils.core import setup

long_description = """\
PyG3T, the Python gettext Translation Toolkit, is a collection of
tools for working with GNU gettext translation files."""

packages = ['pyg3t']
scriptnames = ['gtabc.py', 'gtgrep.py', 'gtdiff.py', 'gtxml.py']
scripts = ['pyg3t/%s' % scriptname 
           for scriptname in scriptnames]

# TODO
# what should we do about versions?
# url should probably point to somewhere useful, i.e. with documentation
# maintainer_email ?
# what about a bin/ directory for the scripts?
# (maybe that will make it easier to change command line settings, for example)

setup(name='pyg3t',
      version='0.1',
      description='PyG3T, python gettext translation toolkit',
      url='https://code.launchpad.net/~pyg3t-dev-team/pyg3t/trunk',
      maintainer='PyG3T development team',
      #maintainer_email='',
      license='GPL',
      platforms=['linux'],
      packages=packages,
      scripts=scripts,
      long_description=long_description)
