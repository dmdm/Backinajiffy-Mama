.. _tutorial:

========
Tutorial
========

To explore the features of :mod:`mama`, let's build a small command-line
application and gradually add some commands to it.

You can find the code to follow the steps in folder 'demos/step_*'.

We recommend that you create a Python virtual environment and install :mod:`mama` there.

.. code-block:: bash

    # Create the virtual environment
    python -mvenv mama-demo-venv
    # Activate it
    . mama-demo-venv/bin/activate
    # Go to the folder where mama's "setup.py" resides and install mama
    cd ~/mama  # CHANGE THIS
    pip install -e .


Step 0
------

For convenience, we create a scaffolding that allows us to install the application in
a (virtual) environment of Python.

Strictly speaking, this step is not necessary to create a CLI application with mama, and therefore
we name this step zero and not step one.

So, if you run these commands in a shell::

    cd demos/step_0
    pip install -e .
    mama-demo

you will see this output::

    TODO implement the app


Step 1
------

::

    cd ../step_1
    pip install -e .

In this step we implement the main-function of the application with the help of several :mod:`mama` functions.

:mod:`mama` is based on `asyncio` and therefore :mod:`mama`'s main-function is asynchronous. We need to run it
from within `asyncio` like this::

    def main():
        asyncio.run(amain())

:func:`amain` is just a wrapper around the default implementation of a main-function:
:func:`backinajiffy.mama.cli.default_main`::

    async def amain(argv=None):
        project_name = 'mama-demo'
        project_logger_name = 'mama-demo'
        arg_parser = make_default_arg_parser(project_name=project_name,
                                             module=None
                                             )
        await default_main(
            project_name=project_name,
            project_logger_name=project_logger_name,
            argparser=arg_parser,
            argv=argv,
            debug_args=True
        )

Here we inform :mod:`mama` about our project (`project_name`, `project_logger`) and tell her that we want to have
a log line on DEBUG level with the parsed command-line arguments (`debug_args=True`).

We also need to give an instance of an argument parser to :mod:`mama`. This argument parser will eventually be able
to detect which commands we have implemented and to load them automatically. At the moment we do not have such
and therefore do not specify the module that hosts the commands (`cmd_module=None`).

In case you want to provide your own list of argument values, just specify `argv`. By default it is None
and then the argument parser uses `sys.argv[1:]`.

If we now run the app again::

    mama-demo

we will get two lines of output:

.. code-block:: text

    No module for sub-commands given
    2021-03-09T19:27:40+0100 MainProcess MainThread mama-demo    CRITICAL Please call a sub-command {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 327}

The first line is a message logged before logging was initialized. It warns us, that we did not specify a module with
the commands--which we intended.

The second line is an actual, nicely formatted log-message from :mod:`mama`. Our CLI application does not
do anything useful without any command, and thus terminates with a critical error. This is also reflected
by its exit code being :const:`backinajiffy.mama.cli.EXIT_CODE_FATAL`::

    echo $?
    99

But already a couple of default CLI arguments are available and are processed by :mod:`mama`:

.. code-block:: text

    mama-demo -h

    usage: mama-demo [-h] [-v] [--log-file LOG_FILE] [-q] [-F {txt,ptxt,json,yaml}] [-O FILENAME] [-c CONF]

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Set verbosity, use multiple times to be increasingly verbose (None: error, v: warning, vv: info, vvv: debug, 4*v: Set libraries to log on debug level, 5*v: set event loop in debug mode). (default: None)
      --log-file LOG_FILE   Write logs into this file (default: None)
      -q, --quiet           Do not log any message, you need to inspect exit code. (default: False)
      -F {txt,ptxt,json,yaml}, --output-format {txt,ptxt,json,yaml}
                            Output format (default: txt)
      -O FILENAME, --output-file FILENAME
                            Output file (default: None)
      -c CONF, --conf CONF  Read this config file (yaml or json) (default: ./rc.yaml)

Try some:

.. code-block:: text

    mama-demo -vvv -F json -O /tmp/foo.txt

Notice the DEBUG message with the parsed arguments (which we requested above with `debug_args=True`):

.. code-block:: text

    2021-03-09T19:43:58+0100 MainProcess MainThread mama-demo    DEBUG    Namespace(verbose=3, log_file=None, quiet=False, output_format='json', output_file='/tmp/foo.txt', conf='./rc.yaml') {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 423}

Notice also that :mod:`mama` fully initialized Python's logging infrastructure and gives us an ISO timestamp, the names
of the current process and thread, and also indicates the source file and line number that logged this message.

To see the debug message with the CLI arguments, we needed to set the log level to DEBUG (`-vvv`). Now also
INFOs and WARNINGs are logged: :mod:`mama` informs us when she was started, when she ended and how long she ran.

.. code-block:: text

    2021-03-09T19:43:58+0100 MainProcess MainThread mama-demo    INFO     Start mama-demo {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 426}
    2021-03-09T19:43:58+0100 MainProcess MainThread mama-demo    CRITICAL Please call a sub-command {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 327}
    2021-03-09T19:43:58+0100 MainProcess MainThread mama-demo    INFO     End mama-demo, 0.0002 secs taken {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 431}


Step 2
------

::

    cd ../step_2
    pip install -e .

Now we can add our first command. It shall be called "hello" and print out "Hello world.". :mod:`mama` wants each
command to be a python file, and needs all of them to be located in a particular package. The name and location of
that package we can choose freely, and in this example we want to call it `cmds` and locate it inside package
`mama_demo`.::

    mkdir mama_demo/cmds
    touch mama_demo/cmds/__init__.py

Inform the argument parser in `__main__` about this "commands" package to let it automatically read any new command we
will create::

    import mama_demo.cmds
    arg_parser = make_default_arg_parser(project_name=project_name,
                                         cmd_module=mama_demo.cmds
                                         )

Inside 'mama_demo/cmds' create a file called 'hello.py' with this content::

    import argparse
    from typing import Any

    from backinajiffy.mama import cli

    CMD = __name__.split('.')[-1].replace('_', '-')


    def add_subcommand(sps: argparse._SubParsersAction):
        p = sps.add_parser(CMD, help='The first command')
        p.set_defaults(cmd=HelloCmd)


    class HelloCmd(cli.BaseCmd):

        async def get_result(self) -> Any:
            return 'Hello world.'

A command needs a small scaffolding: a function :func:`add_subcommand` to add the command to an existing argument
parser, and a class, derived from :class:`backinajiffy.mama.cli.BaseCmd` to implement the functionality of the command.

The help text lists our "hello" command:

.. code-block:: text

    mama-demo -h
    ...
    positional arguments:
      {hello}               Commands
        hello               The first command
    ...

And the help of our new command is available with:

.. code-block:: text

    $ mama-demo hello -h
    usage: mama-demo hello [-h]

    optional arguments:
      -h, --help  show this help message and exit

When we execute the command, we get the intended output:

.. code-block:: text

    $ mama-demo hello
    Hello world.

Log level DEBUG gives us information about the command :mod:`mama` executed:

.. code-block:: text

    $ mama-demo -vvv hello
    Hello world.
    2021-03-12T12:31:04+0100 MainProcess MainThread mama-demo    DEBUG    Namespace(verbose=3, log_file=None, quiet=False, output_format='txt', output_file=None, conf='./rc.yaml', cmd=<class 'mama_demo.cmds.hello.HelloCmd'>) {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 423}
    2021-03-12T12:31:04+0100 MainProcess MainThread mama-demo    INFO     Start mama-demo {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 426}
    2021-03-12T12:31:04+0100 MainProcess MainThread mama-demo    DEBUG    Running subcommand '<class 'mama_demo.cmds.hello.HelloCmd'>' {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 330}
    2021-03-12T12:31:04+0100 MainProcess MainThread mama-demo    INFO     End mama-demo, 0.0004 secs taken {"f": "/home/dm/myprojects/FrogSpace9/mama/backinajiffy/mama/cli.py", "l": 431}

No worries, the log messages will not clutter your result when you want to pipe it into a file: :mod:`mama` logs by
default to STDERR. Also, you could instruct the command to save the output to a file in the first place:

.. code-block:: text

    $ mama-demo -vvv -O /tmp/hello.txt  hello
    # ...log messages here...
    $ cat /tmp/hello.txt
    Hello world.

To add more commands, simply create more files with above structure in the "commands" package.

This concludes our tutorial. To learn more about individual features of :mod:`mama`, head over to section "Howtos".
