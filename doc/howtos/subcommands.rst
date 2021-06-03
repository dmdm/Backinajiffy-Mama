.. _subcommands:

============
Sub-Commands
============

In the tutorial you have seen how to create new commands by adding Python modules to the "commands" folder:

.. code-block:: text

    cmds
     +-- __init__.py
     +-- hello.py                  <-- Command "hello"

Mama allows you to create nested commands by adding additional folders, like this:

.. code-block:: text

    cmds
     +-- __init__.py
     +-- hello.py
     +-- stars                 <-- Command "stars" that has sub-commands
          +-- __init__.py     <-- this needs some code!
          +-- gaze.py          <-- Command "stars gaze"
          +-- download.py      <-- Command "stars download"

To initialize a sub-folder in 'cmds' as a command, you need to write this code into the '__init__' file::

    import argparse
    import sys

    from backinajiffy.mama.cli import import_subcommands

    CMD = __name__.split('.')[-1].replace('_', '-')


    def add_subcommand(sps: argparse._SubParsersAction):
        p = sps.add_parser(CMD, help='Perform actions on stars')
        import_subcommands(p, sys.modules[__name__])
