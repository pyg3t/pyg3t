.. PyG3T documentation master file, created by
   sphinx-quickstart on Mon Jun  1 15:01:29 2015.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Welcome to PyG3T's documentation!
=================================

PyG3T (short for Python GetText Translation Toolkit) is a set of pure Python
tools to work with gettext catalogs (.po-files) as a translator.

The toolkit consists of:

 * **gtcat**: write a catalog in normalized format, or change encoding
 * **gtcheckargs**: parse translations of command line options in a catalog, checking for errors (designed for GNU coreutils and similar)
 * **gtcompare**: compare two catalogs qualitatively
 * **gtgrep**: perform string searches within catalogs
 * **gtmerge**: combine two or more catalogs in different ways
 * **gtprevmsgdiff**: show a word-wise diff which compares old msgids in a catalog with current ones
 * **gtwdiff**: show an ordinary podiff as a word-wise podiff
 * **poabc**: check for common translation errors, such as missing punctuation
 * **podiff**: generate diffs of po-files, such that each differing entry is printed completely
 * **popatch**: apply a podiff to an old catalog to obtain the new catalog
 * **gtxml**: check xml in translations

Contents:

.. toctree::
   :maxdepth: 2

   getting_started
   examples
   api_documentation
   glossary

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`

