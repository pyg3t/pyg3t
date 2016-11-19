Examples
========

gtcat
-----

Write catalog to stdout with syntax coloring::

  gtcat -c file.po

Change encoding of file to UTF-8::

  gtcat --encoding utf-8 file.po > file.utf8.po

podiff
------

The main application of podiff is to generate a diff where the
translator has added and changed some strings or comments.  Generate a
diff of two catalogs::

  podiff old.po new.po > differences.podiff

If the two catalogs have different English strings, the above
will cause an error, because we expect only the translator to have
been at work.  To override this and produce a diff with all changes,
including addition and removal of English strings, use::

  podiff old.po new.po --full > differences.full.podiff

gtcompare
---------

You get a file from Launchpad and another from debian for the same translation, but with different contents::

  gtcompare file1.po file2.po

This will print something like::

  Template of second file is more recent
  Translations in first file were revised more recently

  Total number of messages increased by 1849 from 193 to 2042.

  49 msgids removed [u:   0, f:   0, t:  49].
  1898 msgids added   [u: 176, f: 307, t:1415].
  144 msgids in common.

  0 messages remain untranslated.
  0 untranslated messages changed to fuzzy.
  0 untranslated messages changed to translated.
  0 fuzzy messages changed to untranslated.
  0 messages remain fuzzy.
  0 fuzzy messages changed to translated.
  53 translated messages changed to untranslated.
  87 translated messages changed to fuzzy.
  4 messages remain translated.


Miscellaneous
-------------

Update an outdated podiff (program.podiff) to match the msgid of a
newer version (master.po), and regenerate the diff::

  popatch program.podiff --new > new.po
  gtmerge new.po master.po > merged.po
  podiff master.po merged.po > program.new.podiff

The diff will only include those messages that are still present in
the new template.  Often it might be a good idea to use msgmerge
instead of gtmerge to preserve fuzzy messages.

This command does the same, but in one line::

  popatch program.podiff --new | gtmerge - master.po | podiff master.po - > program.new.podiff

