.. _errorhandling:

==============
Error Handling
==============

Typically, you implement your command by overriding method :meth:`backinajiffy.mama.cli.BaseCmd.get_result`. This way
Mama can wrap it in a try..catch block and makes sure that no exception goes by unlogged.

If your program exits as expected, Mama returns exit code 0 (as defined in :const:`backinajiffy.mama.cli.EXIT_CODE_OK`).

Mama treats any unhandled exception as a fatal error and returns exit code 99 (as defined in
:const:`backinajiffy.mama.cli.EXIT_CODE_FATAL`).

To hook into this mechanism and catch specific exceptions to return your own exit code, you need to tell your
command about them. By default, Mama catches exceptions derived from :class:`backinajiffy.mama.exc.MamaError`.
Implement the module for your command like this::

    EXIT_CODE_ERROR = 10   # <-- define your own exit code here; Mama's default is 1

    class MyCmd(cli.BaseCmd):

        def __init__(self, args):
            super().__init__(...
                             # define the list of exceptions that you want Mama to catch
                             catch=(asyncio.TimeoutError, asyncssh.process.ProcessError),
                             exit_code_error = EXIT_CODE_ERROR
                            )

In case you need to clean up after your command, whether it exited successfully or with an error, give Mama a
callback function::

    class MyCmd(cli.BaseCmd):

        def __init__(self, args):
            super().__init__(...
                             finally_cb=self.close
                            )

        async def close(self):
            pass  # Close open connections, or perform some other cleanups


TODO explain error chaining
