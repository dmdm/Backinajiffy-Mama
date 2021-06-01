"""
Module with helpers to execute commands remotely and locally.
"""

import functools
import logging
import os
import subprocess
import traceback
from argparse import ArgumentParser
from typing import List
from urllib.parse import urlparse

import paramiko
import paramiko.ssh_exception as ssh_exc

from .exc import MamaError

CMD_TIMEOUT = 10
SSH_PORT = 22


def get_module_logger():
    return logging.getLogger(__name__)


class RemoteError(MamaError):
    pass


def add_cli_arguments(p: ArgumentParser, required=False) -> None:
    """
    Adds set of arguments to given parser needed to connect to remote host and run commands there.

    :param p: ArgumentParser
    :param required: Whether or not argument '--remote' shall be mandatory.
    """
    gr = p.add_argument_group('Remote', 'Arguments to execute a command remotely via SSH')
    gr.add_argument(
        '--remote',
        required=required,
        help='Execute command remotely on this host.'
             ' URI format, e.g. ssh://user:pwd@1.2.3.4:5555 or just ssh://1.2.3.4:5555 if you provide a key file.'
    )
    gr.add_argument(
        '--key-file',
        help='Filename of the public key to use instead of username/password'
    )
    gr.add_argument(
        '--passphrase',
        help='Passphrase to decrypt key'
    )
    gr.add_argument(
        '--sudo',
        action='store_true',
        help='Execute command as root with sudo. If set, we need a password in --remote.'
    )
    gr.add_argument(
        '--cmd-timeout',
        type=int,
        default=CMD_TIMEOUT,
        help='Timeout for the remote command in seconds. Set to -1 to use default of current command '
             '(which may be different from the general default of remote commands).'
    )


def resolve_cli_arguments(args) -> dict:
    """
    Resolves arguments into a dict.

    :param args: Namespace with arguments as created by ArgumentParser.parse()
    :return: Dict with all arguments.
    """
    d = {}
    if args.remote:
        r = urlparse(args.remote)
        d = {
            'user': r.username,
            'pwd': r.password,
            'host': r.hostname,
            'port': r.port if r.port else SSH_PORT,
        }
    if args.key_file:
        d['key_file'] = args.key_file
    if args.passphrase:
        d['passphrase'] = args.passphrase
    d['sudo'] = args.sudo
    d['cmd_timeout'] = args.cmd_timeout
    return d


def conn_args(remote_args) -> dict:
    """
    Filters dict of args for those needed to create a connection.

    :param remote_args: Dict with all arguments.
    :return: Dict with arguments to make a connection.
    """
    d = remote_args.copy()
    del d['sudo']
    del d['cmd_timeout']
    return d


def run(cmd, host, user=None, pwd=None, port=22, key_file=None, passphrase=None, cmd_timeout=CMD_TIMEOUT, sudo=False):
    """
    Connects to remote host via SSH and runs command there.

    :param cmd:
    :param host:
    :param user:
    :param pwd:
    :param port:
    :param key_file:
    :param passphrase:
    :param cmd_timeout:
    :param sudo: If True, command is run as root with 'sudo'
    :return: List[str]
    :raise: :class:`RemoteError`
    """
    ssh = None
    try:
        ssh = connect(host=host, port=port, user=user, pwd=pwd,
                      key_file=key_file, passphrase=passphrase)
        return run_cmd(ssh, cmd, sudo=sudo, pwd=pwd, timeout=cmd_timeout)
    finally:
        if ssh:
            ssh.close()


def connect(host, user=None, pwd=None, port=22, key_file=None, passphrase=None):
    """
    Connects to host and returns SSHClient.

    :param host:
    :param user:
    :param pwd:
    :param port:
    :param key_file:
    :param passphrase:
    :return: SSHClient
    :raise: :class:`RemoteError`
    """
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
    try:
        ssh.connect(hostname=host, port=port, username=user, password=pwd,
                    key_filename=key_file, passphrase=passphrase)
    except (ssh_exc.SSHException, ssh_exc.NoValidConnectionsError) as exc:
        raise RemoteError('Failed to connect') from exc
    return ssh


def run_cmd(ssh, cmd, sudo=False, pwd=None, timeout=CMD_TIMEOUT):
    """
    Runs command on given SSHClient.

    :param ssh:
    :param cmd:
    :param sudo: If True, command is run as root with 'sudo'
    :param pwd:
    :param timeout:
    :return: List[str]
    :raise: :class:`RemoteError`
    """
    if timeout == 0:
        timeout = None
    if timeout:
        timeout = float(timeout)
    if not isinstance(cmd, str):
        cmd = ' '.join(cmd)
    if sudo:
        cmd = f"sudo -S -p '' {cmd}"
    try:
        stdin, stdout, stderr = ssh.exec_command(cmd, timeout=timeout)
        if sudo:
            stdin.write(pwd + "\n")
            stdin.flush()
        out = [s.strip() for s in stdout.readlines()]
        err = [s.strip() for s in stderr.readlines()]
        retval = stdout.channel.recv_exit_status()
        if err and retval != 0:
            raise RemoteError('({}) {}'.format(retval, r'\n'.join(err)))
        if retval != 0:
            raise RemoteError('({}) unknown error'.format(retval))
        return out
    except ssh_exc.SSHException as exc:
        raise RemoteError('Failed to run') from exc


def run_locally(cmd, sudo=False, pwd=None, timeout=CMD_TIMEOUT):
    """
    Runs command locally.

    :param cmd:
    :param sudo:
    :param pwd:
    :param timeout:
    :return: List[str]
    :raise: RemoteError
    """
    lgg = get_module_logger()
    if sudo:
        lgg.warning('Running sudo locally is not implemented yet')
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as exc:
        raise RemoteError('Failed to run locally') from exc
    else:
        if p.returncode != 0:
            m = r'\n'.join(p.stderr.decode('utf-8').strip().split("\n"))
            raise RemoteError('Failed to run locally: ({}) {}'.format(p.returncode, m))
        return p.stdout.decode('utf-8').split("\n")


def get_run(ssh=None, sudo=False, pwd=None, timeout=CMD_TIMEOUT):
    """
    Returns partially filled function to run command.

    Abstracts distinction between locally and remotely run commands.

    :param ssh: Optional. If given, returns function for remote execution, else for local execution.
    :param sudo:
    :param pwd:
    :param timeout:
    :return: Partially filled function to run command.
    """
    if ssh:
        _run = functools.partial(run_cmd, ssh=ssh, sudo=sudo, pwd=pwd, timeout=timeout)
    else:
        _run = functools.partial(run_locally, sudo=sudo, pwd=pwd, timeout=timeout)
    return _run


def get_run_fs(ssh=None, sudo=False, pwd=None, timeout=CMD_TIMEOUT):
    """
    Returns partially filled function to run command and a filesystem object.

    Abstracts distinction between locally and remotely run commands. Filesystem object is Python's os for
    local execution and SFTPClient for remote execution (both sport similar APIs).

    :param ssh: Optional. If given, returns function for remote execution, else for local execution.
    :param sudo:
    :param pwd:
    :param timeout:
    :return: 2-tuple: Partially filled function to run command, filesystem object.
    """
    if ssh:
        _run = functools.partial(run_cmd, ssh=ssh, sudo=sudo, pwd=pwd, timeout=timeout)
        _fs = ssh.open_sftp()
    else:
        _run = functools.partial(run_locally, sudo=sudo, pwd=pwd, timeout=timeout)
        _fs = os
    return _run, _fs


def fetch_hostname(ssh=None, timeout=CMD_TIMEOUT):
    """
    Returns hostname.

    :param ssh:
    :param timeout:
    :return:
    """
    _run = get_run(ssh=ssh, timeout=timeout)
    cmd = 'hostname'
    out = _run(cmd=cmd)
    return get_first_line(out)


def fetch_timedate_info(dst_fn=None, ssh=None, timeout=CMD_TIMEOUT) -> List[str]:
    """
    Returns timedate info given by `timedatectl` and optionally writes it to a file.

    :param dst_fn: If given, info will be written into this file additionally to be returned
    :param ssh:
    :param timeout:
    :return: Timedate info
    """
    _run = get_run(ssh=ssh, timeout=timeout)
    cmd = 'timedatectl'
    if dst_fn:
        # CAVEAT: piping into tee will return us exit code of tee, not of timedatectl!
        cmd += f' | tee "{dst_fn}"'
    return _run(cmd=cmd)


def mk_temp_dir(ssh=None, timeout=CMD_TIMEOUT):
    """
    Creates a temporary directory in safe way and returns its path.

    :param ssh:
    :param timeout:
    :return: Path of created directory.
    """
    _run, _fs = get_run_fs(ssh=ssh, timeout=timeout)
    cmd = 'mktemp -d --tmpdir mama-$(hostname).XXXXX'
    try:
        tmpdir = get_first_line(_run(cmd=cmd))
        _fs.chdir(tmpdir)
        return _fs.getcwd()
    finally:
        if ssh and _fs:
            _fs.close()


def get_first_line(out: List[str]):
    """
    Returns first line of command's output in a safe way.

    :param out: List of strings containing command's output.
    :return: First line
    :raise: :class:`RemoteError` if :param:`out` does not have index 0.
    """
    try:
        return out[0]
    except IndexError as exc:
        raise RemoteError("Unexpected output of mktemp (seems not to be List[str]): '{out}'") from exc


def tar(fn: str, sources: List[str], ssh=None, pwd=None, timeout=CMD_TIMEOUT) -> str:
    """
    Creates archive.

    If source paths share common prefix with the archive file, this part of the path is removed, e.g.

        tar cf /tmp/arc.tar /tmp/foo /a/b/c
        -> foo
        -> a/b/c

    Compression is selected by tar itself based on its file extension.

    :param fn: Path of archive file to create.
    :param sources: List of things to archive.
    :param ssh:
    :param pwd: Optional password. If given, we run as root using sudo.
    :param timeout:
    :return: Full path of created archive file.
    """
    lgg = get_module_logger()
    sudo = True if pwd is not None else False
    _run = get_run(ssh=ssh, sudo=sudo, pwd=pwd, timeout=timeout)

    dst_dir = os.path.dirname(fn)
    sources2 = []
    for s in sources:
        cp = os.path.commonpath([dst_dir, s])
        if cp:
            s = s[len(cp):].lstrip(os.path.sep)
        sources2.append(s)
    sources2 = ' '.join(sources2)
    cmd = f'tar caf {fn} -C {dst_dir} {sources2}'  # auto-compress based on suffix
    lgg.debug(cmd)
    _run(cmd=cmd)
    lgg.debug(get_first_line(_run(cmd='ls -l ' + fn)))
    return fn


def download_file(fn, dst_fn, ssh=None, timeout=CMD_TIMEOUT):
    """
    Downloads a file.

    :param fn: Remote file to download.
    :param dst_fn: Name of local file it will become
    :param ssh:
    :param timeout:
    :return:
    """
    lgg = get_module_logger()
    _run, _fs = get_run_fs(ssh=ssh, timeout=timeout)
    try:
        _fs.get(fn, dst_fn)
        lgg.info(f"File '{fn}' downloaded to '{dst_fn}'")
    finally:
        if ssh and _fs:
            _fs.close()
