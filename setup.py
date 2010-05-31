#!/usr/bin/env python

# Copyright (C) 2009-2010 PyG3T development team
# Please see the accompanying LICENSE file for further information.

from distutils.core import setup
import pyg3t

long_description = """\
PyG3T, the Python gettext Translation Toolkit, is a collection of
tools for working with GNU gettext translation files."""

packages = ['pyg3t']
scriptnames = ['gtgrep', 'gtxml', 'podiff', 'poabc', 'poselect']
scripts = ['bin/%s' % scriptname 
           for scriptname in scriptnames]

setup(name='pyg3t',
      version=pyg3t.__version__,
      author='PyG3T development team',
      #author_email='',
      maintainer='PyG3T development team',
      #maintainer_email='',
      url='https://launchpad.net/pyg3t',
      description='PyG3T, python gettext translation toolkit',
      long_description=long_description,
      download_url='https://launchpad.net/pyg3t/+download',
      #classifiers=[],
      platforms=['linux'],
      packages=packages,
      scripts=scripts,
      license='GPL')
