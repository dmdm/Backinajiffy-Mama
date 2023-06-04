.. _cliarguments:

=============
CLI Arguments
=============

By default, Mama implements the following CLI arguments and also shows the defualt values in the help text::

    $ mama-demo -h
    usage: mama-demo [-h] [-v] [--log-file LOG_FILE] [-q] [-F {txt,ptxt,json,yaml}] [-O FILENAME] [-c CONF] {hello} ...

    positional arguments:
      {hello}               Commands
        hello               The first command

    optional arguments:
      -h, --help            show this help message and exit
      -v, --verbose         Set verbosity, use multiple times to be increasingly verbose (None: error, v: warning,
                            vv: info, vvv: debug, 4*v: Set libraries to log on debug level, 5*v: set event loop in
                            debug mode). (default: None)
      --log-file LOG_FILE   Write logs into this file (default: None)
      -q, --quiet           Do not log any message, you need to inspect exit code. (default: False)
      -F {txt,ptxt,json,yaml}, --output-format {txt,ptxt,json,yaml}
                            Output format (default: txt)
      -O FILENAME, --output-file FILENAME
                            Output file (default: None)
      -c CONF, --conf CONF  Read this config file (yaml or json) (default: None)



Custom Arguments
================

Provide arguments for your command by implementing the following function in the module of your command::

    def add_subcommand(sps: argparse._SubParsersAction):
        p = sps.add_parser(CMD, help='This is my command')
        p.add_argument(
            '-p', '--processes',
            default=multiprocessing.cpu_count(),
            type=int,
            help='Number of concurrent processes'
        )
        p.add_argument(
            '-t', '--tasks',
            default=1,
            type=int,
            help='Number of async tasks within same process'
    )
        p.set_defaults(cmd=MyCmd)


    class MyCmd(cli.BaseCmd):
        def __init__(self, args):
            super().__init__(args=args, finally_cb=self.close,
                             catch=(asyncio.TimeoutError, asyncssh.process.ProcessError),
                             lgg=logging.getLogger(PROJECT_LOGGER_NAME + '.' + self.__class__.__name__))
            self.processes = args.processes
            self.tasks = args.tasks

        # ...
