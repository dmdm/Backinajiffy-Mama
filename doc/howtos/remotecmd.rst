.. _remotecmd:

==============
Remote Command
==============

Mama includes facilities to execute a command on a remote machine via SSH:

.. code-block:: text

    Arguments to execute a command remotely via SSH

      -R REMOTES, --remote REMOTES
                            Execute command remotely on this host. URI format, e.g. ssh://user:pwd@1.2.3.4:5555 or just
                            ssh://1.2.3.4:5555 if you provide a key file. Repeat this argument if you have multiple
                            remotes. Additional remotes can be just an IP address or a hostname. If so, they are
                            inserted into the SSH URL created from the first remote. (default: None)
      --sudo                Execute command as root with sudo. If set, we need a password in --remote. (default: False)
      -J JUMP_HOSTS, --jump-host JUMP_HOSTS
                            Use this host as a jump-host. Repeat this argument if you have multiple jump hosts. URI
                            format, e.g. ssh://user:pwd@1.2.3.4:5555 or just ssh://1.2.3.4:5555 if you provide a key
                            file. (default: None)
      --cmd-timeout CMD_TIMEOUT
                            Timeout for the remote command in seconds (default: 10)
      --login-timeout LOGIN_TIMEOUT
                            Timeout for logging in at the remote host (default: 120)
      --strict-host-key-checking
                            Validate the server host key presented during the SSH handshake (default: False)

Add the additional CLI arguments to your command with the help of :func:`backinajiffy.mama.remote.add_cli_arguments`
like this::

    from backinajiffy.mama.remote import add_cli_arguments, resolve_cli_arguments


    def add_subcommand(sps):
        p = sps.add_parser(CMD, help='My command help')

        # -v--- add the remote args
        add_cli_arguments(p, required=True, cmd_timeout=CMD_TIMEOUT)

        # your args here
        p.add_argument(...)
        p.set_defaults(cmd=MyCmd)

Fetch the arguments in your command like this::

    class MyCmd(cli.BaseCmd):

        def __init__(self, args):
            super().__init__(...)
            self.remotes = resolve_cli_arguments(args)

`self.remotes` contains the parsed list of remotes that you could use like this:

.. code-block::

    # ...
    for remote in self.remotes:
        run_task_on_remote(remote, task_func)
    # ...

    async def run_task_on_remote(remote, task_func):
        lgg = module_logger()
        lgg.debug('Processing ' + str(remote['end_host']['host']))

        connections = []
        try:
            connections = await mama_remote.connect(remote)
            conn = connections[-1]
            return await task_func(remote, conn)
        except asyncio.TimeoutError as e:
            lgg.error('Failed task: Timed out', extra={'data': {'error': repr(e), 'task_func': task_func, 'remote': remote}})
        except (asyncssh.Error, socket.error, ConnectionError) as e:
            lgg.error('Failed task', extra={'data': {'error': e, 'task_func': task_func, 'remote': remote}})
        finally:
            for c in reversed(connections):
                try:
                    c.close()
                except ConnectionError as e:
                    lgg.error('Failed to close connection', extra={'data': {'error': str(e), 'task_func': task_func, 'connection': c}})

        lgg.debug('Finished ' + str(remote['end_host']['host']))

Above example encapsulates running the remote command and all the necessary error handling. Alternatively, e.g. in
case you only want to run on a single remote machine, you could think about facilitating the clean-up callback
finally_cb`. Mama can tunnel to the destination machine via multiple jump hosts (CLI argument `-J/--jump-host`),
therefore we need to handle a list of connections (of which the last one is the connection to the destination).

Here is an example of a "task_func" that uses :func:`backinajiffy.mama.remote.run_cmd_logged` to run the command on the
remote machine, check its exit code and, in case of an error, to log all necessary information::

    async def task_func(remote, conn):
        return await fetch_crm_status(
            conn=conn,
            sudo_pwd=remote.get('sudo_pwd'),
            timeout=remote['cmd_timeout']
        )

    async def fetch_crm_status(conn, sudo_pwd=None, timeout: Optional[int] = CMD_TIMEOUT) -> str:
        """
        Fetches CRM status from remote host.

        :param conn: Open connection
        :param sudo_pwd: Password for sudo
        :param timeout: Timeout for this command
        :return: Output of 'crm status' as XML-string
        """
        lgg = module_logger()
        lgg.debug(f"Fetching CRM status")
        cmd = ['crm', 'status', '-X']
        r = await run_cmd_logged(lgg,
                                 conn,
                                 cmd,
                                 sudo=sudo_pwd,
                                 encoding=None,
                                 timeout=timeout)
        return r.stdout.decode('utf-8')

.. note:: See module :mod:`backinajiffy.mama.remote` for more useful helpers

.. note:: Above example is taken from Mama's experimental implementation of running parallel tasks in module
    module :mod:`backinajiffy.mama.parallel`.
