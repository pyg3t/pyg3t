Glossary
========

.. glossary::
   :sorted:

   chunk
      Chunk refer to the chunk of text in a .po file that corresponds to a
      :term:`message`. The whole file consist of such chunks separated by a
      blank line. See the entry for :term:`message` for an example of what a
      chunk looks like.
      
   fuzzy
      FIXME
      
   gettext catalog
      A gettext catalog is a collection of gettext :term:`message` s and a
      header with metadata. It is most often contained in a .po file. The
      header is the message with and empty :term:`msgid` and is usually the
      first message of the file.

   message
      A message refers to all data and metadata pertaining to a single
      translatable string in a :term:`gettext catalog`. The data consist of the
      :term:`msgid` (original string) and the :term:`msgstr` (translated
      string), both of which can optionally have plural forms. The metadata
      consist of references to source code lines for the msgids and optionally
      a comment, context and a previous version of the msgid.

      A typical message could look like this (inspired by the Danish translation
      of nautilus) (FIXME better example):

      .. code-block:: po

        # Ahh, nautilus can run programs
        #: ../data/nautilus-autorun-software.desktop.in.in.h:1
        msgid "Run Software"
        msgstr "Kør programmer"	    

   msg
      See :term:`message`

   msgid
      FIXME

   msgstr
      FIXME
