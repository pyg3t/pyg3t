#!/usr/bin/env python

# Copyright (C) 2009-2016 PyG3T development team
# Please see the accompanying LICENSE file for further information.

from distutils.core import setup
import pyg3t
# It seems questionable to import the package when it is not installed.
# But sphinx does it, so it must be okay.

long_description = """\
PyG3T, the Python gettext Translation Toolkit, is a collection of
tools for working with GNU gettext translation files."""

packages = ['pyg3t']
scriptnames = ['gtcat',
               'gtcheckargs',
               'gtcompare',
               'gtgrep',
               'gtmerge',
               'gtprevmsgdiff',
               'gtwdiff',
               'gtxml',
               'poabc',
               'podiff',
               'popatch',
               'poselect']
scripts = ['bin/%s' % scriptname
           for scriptname in scriptnames]

setup(name='pyg3t',
      version=pyg3t.__version__,
      author='PyG3T development team',
      #author_email='',
      maintainer='PyG3T development team',
      #maintainer_email='',
      url='https://github.com/pyg3t/pyg3t',
      description='PyG3T, python gettext translation toolkit',
      long_description=long_description,
      #classifiers=[],
      platforms='all',
      packages=packages,
      scripts=scripts,
      license='GPL')
