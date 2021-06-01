.. Backinajiffy-Mama documentation master file, created by
   sphinx-quickstart on Sat Mar  6 18:24:38 2021.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Backinajiffy-Mama
=================

"The mother of all CLI programs."

Mama helps you to create CLI programs in a jiffy by providing a framework of commonly used facilities, so that you do
not have to code those in every CLI program over and over again.

Here is a quick list of the main features.

* Create commands by simply writing a python module, even nested to create sub(-sub...)-commands
* Fully initialized :ref:`logging`
* All exceptions are caught and logged (:ref:`errorhandling`)
* Well-defined exit codes
* Automatic :ref:`outputformatting` as JSON, YAML, ascii table or plain text
* Write output to a file with a simple CLI argument
* Pre-defined :ref:`cliarguments` for verbosity (log level), output formatting and more
* Provides facilities to run commands on a remote machine (:ref:`remotecmd`)

Get to know Mama by following the :ref:`tutorial` and then read the :ref:`howtos`.


.. toctree::
   :maxdepth: 2
   :caption: Contents:

   tutorial/index
   howtos/index
   api/index


Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
