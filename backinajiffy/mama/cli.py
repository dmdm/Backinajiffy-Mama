import argparse
import asyncio
import collections
import collections.abc
import sys
import time
from pathlib import Path
from pprint import pformat
from importlib import import_module
from argparse import ArgumentParser
from typing import Optional, List, Any, Tuple
import logging
import logging.config
import os
import pkgutil

from tabulate import tabulate
import orjson as json

try:
    from yaml import CDumper as YamlDumper
except ImportError:
    from yaml import Dumper as YamlDumper
import yaml

from backinajiffy.mama.exc import MamaError
from backinajiffy.mama.rc import Rc

from .const import PROJECT_LOGGER_NAME
from .logging import get_error_msg_chain, init_logging

EXIT_CODE_OK = 0
"""Default exit code when script terminates normally."""
EXIT_CODE_FATAL = 99
"""Default exit code when script terminates with a fatal error."""


def module_logger() -> logging.Logger:
    return logging.getLogger(PROJECT_LOGGER_NAME + '.' + __name__)


class BaseCmd:

    def __init__(self,
                 args: argparse.Namespace,
                 cmd_name: Optional[str] = None,
                 lgg: Optional[logging.Logger] = None,
                 catch: Optional[Tuple] = (MamaError,),
                 exit_code_error: Optional[int] = 1,
                 finally_cb=None):
        """
        Base class for a class that implements a particular command.

        TODO Implement reading of config file (arg '--conf')

        :param args: The command-line arguments as returned from Argparser
        :param cmd_name: Name of this command
        :param lgg: Instance of a logger
        :param catch: Tuple of error classes that shall be caught
        :param exit_code_error: Exit code when script terminates with error
        :param finally_cb: Callback that performs additional clean-up after a command has been executed
        """
        # Init common arguments here, e.g.
        #    self.baz = args.baz
        # The implementation should not use 'args' or 'self.args.XXX' but rely solely on instance members.
        self.output_format = args.output_format
        self.output_file = Path(args.output_file) if args.output_file else None
        self.lgg = lgg if lgg else logging.getLogger(PROJECT_LOGGER_NAME + '.' + self.__class__.__name__)
        self.cmd_name = cmd_name
        self.catch = catch
        self.exit_code_error = exit_code_error
        self.finally_cb = finally_cb
        self.output_written = False
        """Whether :meth:`get_result` already has written the output. If True, we do not automatically log info about
        output."""

    async def output(self, data: Any) -> None:
        """
        Writes formatted result data to output stream.

        By default, the output stream is STDOUT, but can also be a file, if argument 'output-file` is given on
        command line.

        :param data: The result data
        """
        if self.output_format == 'json':
            data = json.dumps(data, default=str).decode()
        elif self.output_format == 'yaml':
            data = yaml.dump(data, Dumper=YamlDumper)
        elif self.output_format == 'ptxt':
            data = pformat(data)
        elif self.output_format == 'tsv':
            data = "\n".join(["\t".join([str(c) for c in row]) for row in data])
        await output(data, fn=self.output_file)
        if self.output_file:
            self.lgg.info(f"Output written to file '{self.output_file}'")

    async def format_data(self, data: Any) -> str:
        """
        Formats the result data.

        If requested output format is neither "json", "yaml", "ptext", "tsv", we will format the data here. By default,
        we format sequences and mappings as an ASCII table.

        :param data: Raw result data
        :return: The formatted data as string
        """
        if len(data) > 0 and isinstance(data, collections.abc.Sequence) and not isinstance(data, str):
            if isinstance(data[0], collections.abc.Mapping):
                headers = 'keys'
            else:
                headers = ''
            s = tabulate(data, headers=headers)
            s += "\n({} rows)".format(len(data))
            return s
        else:
            return data

    def can_format_output(self) -> bool:
        """
        Tells whether we can automatically format the result data in the requested format.

        Available formatters are "json", "yaml" , and "ptext" (pretty print). If any other format is requested,
        the child class needs to implement a respective formatter in :meth:`format_data`.

        :return:
        """
        return self.output_format in ('json', 'yaml', 'ptxt', 'tsv')

    async def run(self) -> int:
        """
        Wraps the execution of a command to catch given exceptions and returns a defined exit code.

        Calls :meth:`get_result` to execute the implemented command and get the result data. It then formats the data
        and writes it to the requested output stream, e.g. STDOUT or a file. Lasty, returns EXIT_CODE_OK.

        Catches all exceptions that were given in :meth:`__init__` to return the given `exit_code_error`.

        Finally calls `finally_cb` (if given) to let the command clean-up, e.g. close open connections.

        :return: An exit code
        """
        try:
            data = await self.get_result()
            if data is None:
                if self.output_file and self.output_written:
                    self.lgg.info(f"Output written to file '{self.output_file}'")
                if not self.output_written:
                    self.lgg.info('No data')
            else:
                if not self.can_format_output():
                    data = await self.format_data(data)
                await self.output(data)
            return EXIT_CODE_OK

        # Handle my errors here, others bubble up to main
        except self.catch as exc:
            self.lgg.error("Error executing command '{}': {}".format(self.cmd_name, get_error_msg_chain(exc)),
                           exc_info=True)
            # We can return a non-zero exit-code ourselves
            return self.exit_code_error
        finally:
            # Perform my cleanups here
            self.lgg.debug(f"Cleaning up command '{self.cmd_name}'")
            if self.finally_cb:
                await self.finally_cb()

    async def get_result(self) -> Any:
        """
        Returns the data as result of current command.

        Implement this method in the concrete child class.

        :return: Returns the data that the current command produced or None
        """
        raise NotImplementedError('Implement this in child class')


def get_tty_columns() -> int:
    """
    Returns the width of the TTY

    :return: Number of columns; falls back to 132 if actual width could not be obtained.
    """
    # CAVEAT columns = int(os.environ.get('COLUMNS', 80)) as used in HelpFormatter does not work:
    #        env variable does not exist
    columns = os.environ.get('COLUMNS')
    if columns is not None:
        try:
            # Who knows what the content of that environment variable might be ;)
            columns = int(columns)
        except ValueError:
            columns = None
    if columns is None:
        try:
            # A terminal might not always be present, e.g. when daemonized or run inside PyCharm
            columns, rows = os.get_terminal_size(0)
        except OSError:
            columns = 132
    return columns


def get_help_formatter(prog):
    """
    Returns a help formatter for ArgumentParser that prints default values and uses full width of TTY

    :param prog: Name of the program
    :return: Instance of the help formatter
    """
    return argparse.ArgumentDefaultsHelpFormatter(prog, width=get_tty_columns())


def add_argument(p: ArgumentParser,
                 arg: str,
                 required: Optional[bool] = False,
                 more_help: Optional[str] = None,
                 more_choices: Optional[List[str]] = None,
                 default_value=None):
    """
    Helper to add often-used arguments to given argument parser.

    Available arguments are:

    - verbose
    - log-file
    - quiet
    - output-format
    - output-file

    :param p: Instance of the parser
    :param arg: Name of the argument to add
    :param required: Whether the argument is required
    :param more_help: Additional help text to append to default help text
    :param more_choices: Additional choices to append to default choices
    :param default_value: A default value
    """
    if arg == 'verbose':
        p.add_argument(
            '-v', '--verbose',
            help='Set verbosity, use multiple times to be increasingly verbose '
                 '(None: error, v: warning, vv: info, vvv: debug, '
                 '4*v: Set libraries to log on debug level, '
                 '5*v: set event loop in debug mode).' + (more_help if more_help else ''),
            required=required,
            action='count'
        )
    elif arg == 'version':
        p.add_argument(
            '-V', '--version',
            help='Print version.' + (more_help if more_help else ''),
            required=required,
            action='store_true'
        )
    elif arg == 'log-file':
        p.add_argument(
            '--log-file',
            help='Write logs into this file' + (more_help if more_help else ''),
            required=required
        )
    elif arg == 'quiet':
        p.add_argument(
            '-q', '--quiet',
            help='Do not log any message, you need to inspect exit code.' + (more_help if more_help else ''),
            required=required,
            action='store_true'
        )
    elif arg == 'output-format':
        choices = ['txt', 'ptxt', 'json', 'yaml', 'tsv']
        default = default_value if default_value else choices[0]
        if more_choices:
            choices += more_choices
        p.add_argument(
            '-F', '--output-format',
            help='Output format' + (more_help if more_help else ''),
            required=required,
            choices=choices,
            default=default
        )
    elif arg == 'output-file':
        p.add_argument(
            '-O', '--output-file',
            help='Output file' + (more_help if more_help else ''),
            metavar='FILENAME',
            required=required,
            default=default_value
        )
    elif arg == 'conf':
        p.add_argument(
            '-c', '--conf',
            help='Read this config file (yaml or json)' + (more_help if more_help else ''),
            default=default_value,
            type=Path
        )
    else:
        raise ValueError(f"Unknown argument '{arg}'")


def add_default_arguments(p: ArgumentParser):
    """
    Adds all default arguments to given argument parser.

    :param p: Instance of the parser
    """
    add_argument(p, 'verbose', required=False)
    add_argument(p, 'log-file', required=False)
    add_argument(p, 'quiet', required=False)
    add_argument(p, 'output-format', required=False)
    add_argument(p, 'output-file', required=False)
    add_argument(p, 'conf', required=False)
    add_argument(p, 'version', required=False)


def import_subcommands(p: ArgumentParser, module_with_commands):
    """
    Imports sub-commands from given module and adds them to given argument parser.

    Caller needs to import the module that contains one Python file per sub-command. From this module we automatically
    import all available sub-commands.

    :param p: Instance of ArgumentParser
    :param module_with_commands: The imported module.
    """
    sps = p.add_subparsers(dest='subcmd', help='Commands')
    for _, name, _ in pkgutil.iter_modules(module_with_commands.__path__):
        m = import_module(f'{module_with_commands.__name__}.{name}')
        m.add_subcommand(sps)

    for sp in sps.choices.values():
        sp.formatter_class = get_help_formatter


async def run_subcommand(lgg: logging.Logger, args: argparse.Namespace) -> int:
    """
    Wraps execution of a command to catch all unhandled exceptions.

    :param lgg: Instance of a logger
    :param args: The command-line arguments as returned from Argparser
    :return: The exit code as returned by the command or, EXIT_CODE_FATAL if unhandled exception bubbles up here.
    """
    try:
        if not hasattr(args, 'cmd') or not args.cmd:
            lgg.fatal('Please call a sub-command')
            return EXIT_CODE_FATAL
        else:
            lgg.debug(f"Running subcommand '{args.cmd}'")
            cmd = args.cmd(args, lgg=lgg)
            return await cmd.run()
    except Exception as exc:
        lgg.fatal("Unhandled exception: {}".format(get_error_msg_chain(exc)), exc_info=True)
        return EXIT_CODE_FATAL


def set_log_level(args, libs: Optional[List[str]] = None) -> int:
    """
    Sets log level according to verbosity argument from command-line.

    These are the log levels:

    .. code::

       lvls = {
           -1: logging.CRITICAL,         <--     CLI arg "--quiet"
           0:  logging.ERROR,            <--,    number of '-v'
           1:  logging.WARNING,             |
           2:  logging.INFO,                v
           3:  logging.DEBUG
       }

    Sets the log level also for the given libraries to ERROR, or broader, if requested level is greater 3.

    :param args: The command-line arguments as returned from Argparser
    :param libs: Set also log-level of these libraries
    :return:
    """
    lvls = {
        -1: logging.CRITICAL,
        0:  logging.ERROR,
        1:  logging.WARNING,
        2:  logging.INFO,
        3:  logging.DEBUG
    }
    if libs is None:
        libs = []

    if args.quiet:
        v = -1
    elif args.verbose is None:
        return 0
    else:
        v = args.verbose
    logging.root.setLevel(lvls[v if v <= 3 else 3])
    v = v - 3 if v > 3 else 0
    for n in ['urllib3', 'aiossh', 'asyncio', 'aiohttp', 'mama', 'backinajiffy'] + libs:
        logging.getLogger(n).setLevel(lvls[v if v <= 3 else 3])
    if v >= 3:
        import http.client as http_client
        http_client.HTTPConnection.debuglevel = 1
        asyncio.get_running_loop().set_debug(True)
    return v


async def output(data: Any, fn: Optional[str] = None):
    """
    Helper to print formatted output to file or STDOUT.

    :param data: Formatted result data
    :param fn: Name of the file to write output to
    """
    if fn:
        with open(fn, 'wt', encoding='utf-8') as fp:
            print(data, file=fp)
    else:
        print(data)


async def default_main(project_name: str,
                       project_logger_name: str,
                       argparser: ArgumentParser,
                       argv: Optional[List[Any]] = None,
                       debug_args=False,
                       log_libs: Optional[List[str]] = None,
                       init_func: Optional[Any] = None,
                       project_version: Optional[str] = None
                       ):
    """
    Default implementation of a 'main' function.

    :param project_name: Name of the project
    :param project_logger_name: Name of the logger of this project
    :param argparser: Instance of an argument parser
    :param argv: List of command-line arguments, e.g. `sys.argv[1:]`
    :param debug_args: Whether to log the parsed command-line arguments for debugging
    :param log_libs: Set log-level also for these libraries (these are by default always affected: 'urllib3', 'aiossh',
        'asyncio', 'aiohttp', 'mama', 'backinajiffy')
    :param init_func: Function to perform custom initialisation
    """
    if argv is None:
        argv = sys.argv
    args = argparser.parse_args(argv[1:])
    rc = Rc.create(project_name=project_name, fn_rc=args.conf if args.conf else None)
    rc.add_args(args)
    lc = rc.g('logging')
    init_logging(log_file=args.log_file, config_dict=lc)
    set_log_level(args, libs=log_libs)
    lgg = logging.getLogger(project_logger_name)
    if debug_args:
        lgg.debug(args)
    if args.version:
        if project_version:
            print(f'{project_name} {project_version}')
        else:
            print('No version specified.')
        sys.exit(EXIT_CODE_OK)
    if init_func:
        await init_func(args=args)

    start_time = time.time()
    lgg.info(f'Start {project_name}')

    exit_code = await run_subcommand(lgg, args)
    taken = time.time() - start_time
    lgg.info(f'End {project_name}, {taken:.4f} secs taken')
    sys.exit(exit_code)


def make_default_arg_parser(project_name, cmd_module, project_description=None) -> ArgumentParser:
    p = argparse.ArgumentParser(
        prog=project_name,
        add_help=True,
        description=project_description,
        conflict_handler='resolve',
        formatter_class=get_help_formatter
    )
    add_default_arguments(p)

    if cmd_module:
        import_subcommands(p, cmd_module)
    else:
        module_logger().warning(f'No module for sub-commands given')

    return p
