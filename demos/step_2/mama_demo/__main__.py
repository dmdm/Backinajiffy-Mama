import asyncio

from backinajiffy.mama.cli import default_main, make_default_arg_parser


async def amain(argv=None):
    project_name = 'mama-demo'
    project_logger_name = 'mama-demo'

    from mama_demo import cmds
    arg_parser = make_default_arg_parser(project_name=project_name,
                                         cmd_module=cmds
                                         )
    await default_main(
        project_name=project_name,
        project_logger_name=project_logger_name,
        argparser=arg_parser,
        argv=argv,
        debug_args=True
    )


def main():
    asyncio.run(amain())


if __name__ == '__main__':
    main()
