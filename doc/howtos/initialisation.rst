.. _initialisation:

==============
Initialisation
==============

The tutorial showed the simplest form of initialising the program in file '__main__.py' with the help of Mama's
default methods to create an argument parser and the main function::

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


If you want to perform more actions after Mama has initialised the program, but before she executes the actual command,
provide your own init function::

    async def my_init_func():
        pass

    await default_main(
        # ...
        init_func=my_init_func
    )

See :func:`backinajiffy.mama.cli.default_main` for more details.
