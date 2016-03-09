regml
=====

regml.py is the main entry point for running the XML parser. The parser employs the Click module for handling command-line parameters in a nice way. The general way to call regml.py from the command line is::
  
   regml.py [command] [positional args] (named args)

The command arguments are documented below as functions. The ``[command]`` parameter expected by ``regml.py`` is the name of the function; positional arguments to the function come next, after which come named arguments, specified as standard command-line options. In all arguments, ``_`` is replaced by ``-``.

Example::

   regml.py validate /path/to/reg.xml --no-terms
   regml.py check-terms /path/to/reg.xml --label=1003-1

   

.. py:function:: validate(file, no_terms=False, no_citations=False, no_keyterms=False)

   Validate the specified ``file`` by checking its conformance with the XML schema. Optional flags
   indicate whether to skip checking the validity of term references, citations, and keyterms. If those
   flags are not passed, the validator will automatically make sure that all citations and term
   references point to actually-existing nodes and terms in the regulation tree, and that the keyterms
   are formatted in the appropriate way. Any problems will be reported as either errors or warnings.
   
   :param str file: The path to the XML file to validate.
   :param bool no_terms: Whether to skip validating terms. Defaults to False.
   :param bool no_citations: Whether to skip validating citations. Defaults to False.
   :param bool no_keyterms: Whether to skip validating keyterms. Defaults to False.


.. py:function:: check_terms(file, label=None, term=None)
		 
   Check whether there are any terms that are being used in the reg without being referenced.
   This command initiates an interactive session which presents the user with a possible term
   (highlighted in red) that is being used without a reference. The user is given an option to correct
   this automatically by inserting a reference; if the user chooses this option, the resulting XML
   will be printed for the user in green, with the new inserted text highlighted in red. The user can
   also choose to automatically always fix a reference to a given term, or to always ignore the term.
   At the end of the session, the user is prompted to overwrite the original XML.
		  
   Command line options allow the user to focus only on children of a specific ``label`` or only on a
   specific ``term``. It should be noted that the term finder is a simple string match, so it will
   pick up terms that might happen to be part of larger words (e.g. if `act` is a defined term, then
   `activate` will be picked up as a usage of `act`. Don't automatically approve fixes unless you know
   what you're doing.

   :param str file: The path to the XML file to validate.
   :param bool label: Only validate the children of a specific label.
   :param bool term: Only validate a specific term.

.. py:function:: check_interp_targets(file, label=None):

   Validate the interpretation targets, giving the user an option to overwrite the original file with
   the corrected XML. This functionality is used in situations when the eCFR parser outputs interps with
   incorrect targets, causing them to be attached to the wrong regtext paragraphs. Optional ``label``
   parameter allows the user to validate only children of the specified ``label``.

   :param str file: The path to the XML file to validate.
   :param str label: Only validate children of a specific label.

.. py:function:: json(regulation_files, check_terms=False)

   The ``json`` encapsulates the core functionality for generating JSON output that powers the regsite
   frontend. It accepts any number of ``regulation_files`` and generates the JSON output for every one
   of them. It also generates diffs between every pair of files provided. It is important to make sure
   that the ``regulation_files`` all belong to the same regulation, otherwise the diffs will be meaningless.
   The optional ``check_terms`` flag indicates whether to validate terms while generating JSON.

   :param [str] regulation_files: The list of paths to the XML files from which to generate JSON output.
   :param bool check_terms: Whether to check terms while generating JSON. Defaults to False.

.. py:function:: apply_notice(regulation_file, notice_file)

   Applies the changeset encapsulated in the ``notice_file`` to the ``regulation_file``. The notice indicates
   which version of the regulation it produces; the output is a new file named after the version produced
   by the notice.

   :param str regulation_file: The path to the regulation XML file.
   :param str notice_file: The path to the notice XML file.

.. py:function:: notice_changes(notice_file)

   Lists the changes induced by the notice in the ``notice_file`` and colorizes them according to the
   type of operation indicated (red for delete, yellow for modified, green for added).

   :param str notice_file: The path to the notice XML file.

.. py:function:: apply_notices(cfr_part, version, notices)

   Apply the specified ``notices`` to the XML file specified by the (unique) combination of ``cfr_part`` and
   ``version``. Notices are applied in the order that they are provided, and each notice generates a
   resultant XML file of the full regulation, exactly the same as the :func:`apply_notice` command.

   :param str cfr_part: The number of the CFR part of the reg version to which the notices are to be applied.
   :param str version: The version of the regulation to which the notices are to be applied; usually this is
		       the document number or the document number followed by an underscore and the effective date.
   :param [str] notices: The list of notices to apply in order.

   Example:
   ::
     regml.py 1003 2015-26607_20180101 2015-26607_20190101 2015-26607_20200101

.. py:function:: versions(title, part, from_fr=True)

   List all the notices available for the given title and part. If ``from_fr`` is True, queries the federal register
   API to get a list of available notices. Searches the filesystem starting at the ``XML_ROOT`` for notices
   appltying to this title and part, and prints their document number, their effective date, and which document
   number they apply to.

   :param str title: The CFR title.
   :param str part: The CFR part.
   :param bool from_fr: Whether to query the Federal Register API. Defaults to True.

.. py:function:: ecfr(title, file, act_title, act_section, with_all_versions=False, without_versions=False, without_notices=False, only_notice=None)

   Run the eCFR parser on the provided file obtained from eCFR, and generate a RegML file. Flags control
   how much output the parser generates.

   :param str title: The CFR title.
   :param str file: The XML file in eCFR format to parse.
   :param str act_title: The title of the authorizing act.
   :param str act_section: The section of the authorizing act.
   :param bool with_all_versions: 

.. automodule:: regml
   :members:

