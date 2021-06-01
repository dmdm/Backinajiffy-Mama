import argparse
import logging
from typing import Any

from backinajiffy.mama import cli

# This allows us to use the filename as the command
CMD = __name__.split('.')[-1].replace('_', '-')


def add_subcommand(sps: argparse._SubParsersAction):
    p = sps.add_parser(CMD, help='The first command')
    # Tell the argument parser about the class that implements the command.
    p.set_defaults(cmd=HelloCmd)


# This class implements the command. You can name it any way you want.
class HelloCmd(cli.BaseCmd):

    # Override at least this method, even if the command will not produce output (return None).
    async def get_result(self) -> Any:
        lgg = logging.getLogger()
        data = [
            {'some': 'arbitrary data', 'value': 42},
            {'some': 'more data', 'value': 84}
        ]
        x = 1/0
        return data
