import argparse
import asyncio
import json
import logging
import os
from logging import Logger
from typing import Sequence, Mapping, Any, Optional, List, Dict
from urllib.parse import urlparse
from copy import deepcopy
import re

import asyncssh
from asyncssh import SSHClientConnectionOptions
from backinajiffy.mama.avahi import AVAHI_BROWSE
from .const import PROJECT_LOGGER_NAME

from .exc import MamaError

CMD_TIMEOUT = 10
"""Default timeout for the execution of a remote command."""
LOGIN_TIMEOUT = 2 * 60
"""Default timeout for the login on a remote host."""
SSH_PORT = 22
"""Default port for SSH"""


def module_logger():
    """Helper to return instance of the module logger"""
    return logging.getLogger(PROJECT_LOGGER_NAME + '.' + __name__)


def add_cli_arguments(p: argparse.ArgumentParser, required: Optional[bool] = False,
                      cmd_timeout: Optional[int] = CMD_TIMEOUT, login_timeout: Optional[int] = LOGIN_TIMEOUT) -> None:
    """
    Adds set of arguments needed to connect to remote host and run commands there to given parser.

    :param p: ArgumentParser
    :param required: Whether or not argument '--remote' shall be mandatory.
    :param cmd_timeout: Timeout for the remote command in seconds
    :param login_timeout: Timeout for logging in at the remote host
    """
    gr = p.add_argument_group('Remote', 'Arguments to execute a command remotely via SSH')
    gr.add_argument(
        '-R', '--remote',
        required=required,
        action='append',
        dest='remotes',
        help='Execute command remotely on this host.'
             ' URI format, e.g. ssh://user:pwd@1.2.3.4:5555 or just ssh://1.2.3.4:5555 if you provide a key file.'
             ' Repeat this argument if you have multiple remotes. Additional remotes can be just an IP address or a'
             ' hostname. If so, they are inserted into the SSH URL created from the first remote.'
    )
    gr.add_argument(
        '--sudo',
        action='store_true',
        help='Execute command as root with sudo. If set, we need a password in --remote.'
    )
    gr.add_argument(
        '-J', '--jump-host',
        dest='jump_hosts',
        action='append',
        help='Use this host as a jump-host. Repeat this argument if you have multiple jump hosts.'
             ' URI format, e.g. ssh://user:pwd@1.2.3.4:5555 or just ssh://1.2.3.4:5555 if you provide a key file.'
    )
    gr.add_argument(
        '--cmd-timeout',
        type=int,
        default=cmd_timeout,
        help='Timeout for the remote command in seconds'
    )
    gr.add_argument(
        '--login-timeout',
        type=int,
        default=login_timeout,
        help='Timeout for logging in at the remote host'
    )
    gr.add_argument(
        '--strict-host-key-checking',
        action='store_true',
        help='Validate the server host key presented during the SSH handshake'
    )


def resolve_cli_arguments(args: argparse.Namespace) -> List[Dict]:
    """
    Resolves arguments into a dict.

    :param args: Namespace with arguments as created by ArgumentParser.parse()
    :return: List of dicts with one dict per (jump) host.
    """
    general_args = {
        'jump_hosts':    parse_ssh_urls(args.jump_hosts) if args.jump_hosts else [],
        'sudo':          True if args.sudo else False,
        'cmd_timeout':   args.cmd_timeout,
        'login_timeout': args.login_timeout,
    }
    if not args.strict_host_key_checking:
        general_args['known_hosts'] = None
    rr = []
    for i, ar in enumerate(args.remotes):
        r = {} if i == 0 else deepcopy(rr[i - 1])
        if ar.startswith('ssh://'):
            r['end_host'] = parse_ssh_urls([ar])[0]
        else:
            if i > 0:
                r['end_host']['host'] = ar
            else:
                raise MamaError('1st remote must be complete URL')
        r.update(general_args)
        if r['sudo']:
            r['sudo_pwd'] = r['end_host']['password']
        rr.append(r)
    return rr


def parse_ssh_urls(urls: Sequence[str]) -> Sequence[Mapping[str, Any]]:
    """
    Parses given urls into their components.

    :param urls: List of URLs to parse
    :return: List of dicts with parsed URLs. Cf. `urllib.parse.urlparse`.
    """
    jj = []
    for u in urls:
        o = urlparse(u)
        jj.append({'host':     o.hostname, 'port': o.port if o.port else SSH_PORT, 'username': o.username,
                   'password': o.password})
    return jj


def _wrap_sudo(cmd: str) -> str:
    return f"sudo -S -p '' {cmd}"


async def connect(remote: Mapping[str, Any]) -> Sequence[Any]:
    """
    Connects to remote host.

    Creates an SSH connection, even via jump hosts if those are given.
    """
    cc = []
    hops = [] + remote['jump_hosts'] + [remote['end_host']]
    prev_conn = None
    for hop in hops:
        kw = {k: hop[k] for k in 'host port'.split()}
        if prev_conn:
            kw['tunnel'] = prev_conn
        options = {k: hop.get(k) for k in 'username password'.split()}
        if 'known_hosts' in remote:
            options['known_hosts'] = remote['known_hosts']
        kw['options'] = SSHClientConnectionOptions(**options)
        conn = await asyncssh.connect(**kw)
        cc.append(conn)
        prev_conn = conn
    return cc


async def disk_free(conn, human: Optional[bool] = True, timeout: Optional[int] = CMD_TIMEOUT) -> Any:
    """
    Executes 'df' on remote host.

    :param conn: Open connection
    :param human: Output is human-friendly
    :param timeout: Timeout for this command
    :return: :class:`asyncssh.SSHCompletedProcess`
    """
    args = ['df']
    args += ['-P']
    if human:
        args += ['-h']
    cmd = ' '.join(args)
    return await asyncio.wait_for(conn.run(cmd, check=True), timeout=timeout)


async def avahi_browse(conn, timeout: Optional[int] = CMD_TIMEOUT) -> asyncssh.SSHCompletedProcess:
    """
    Executes 'avahi-browse' on remote host.

    :param conn: Open connection
    :param timeout: Timeout for this command
    :return: :class:`asyncssh.SSHCompletedProcess`
    """
    cmd = ' '.join(AVAHI_BROWSE)
    return await asyncio.wait_for(conn.run(cmd, check=True), timeout=timeout)


async def run_bash_script(conn, fn_script: str, sudo=None, timeout: Optional[int] = CMD_TIMEOUT) -> \
        asyncssh.SSHCompletedProcess:
    """
    Runs given bash script on remote host.

    :param conn: Open connection
    :param fn_script: Filename of the script
    :param sudo: Whether to run script with sudo
    :param timeout: Timeout for this command
    :return: :class:`asyncssh.SSHCompletedProcess`
    """
    args = ['bash']
    args += ['-s']
    if isinstance(sudo, str):
        await asyncio.wait_for(conn.run('cp /bin/bash /tmp', check=True), timeout=timeout)
        with open(fn_script, 'rt', encoding='utf-8') as fp:
            script = fp.read()
        script = sudo + "\n" + script
        args[0] = '/tmp/bash'
        cmd = ' '.join(args)
        cmd = _wrap_sudo(cmd)
        return await asyncio.wait_for(conn.run(cmd, input=script), timeout=timeout)
    else:
        cmd = ' '.join(args)
        return await asyncio.wait_for(conn.run(cmd, stdin=fn_script, check=True), timeout=timeout)


async def run_cmd(conn, cmd: str or List[str], sudo=None, check=True, timeout: Optional[int] = CMD_TIMEOUT,
                  **kwargs) -> asyncssh.SSHCompletedProcess:
    """
    Helper to run a command on a remote host.

    :param conn: Open connection
    :param cmd: The command
    :param sudo: Whether to run command with sudo
    :param check: Whether or not to raise ProcessError when a non-zero exit status is returned. Passed through to
     :meth:`asyncssh.SSHClientConnection.run`
    :param timeout: Timeout for this command
    :param kwargs: Passed through to :meth:`asyncssh.SSHClientConnection.run`
    :return: :class:`asyncssh.SSHCompletedProcess`
    """
    if isinstance(cmd, list):
        cmd = ' '.join(cmd)
    if isinstance(sudo, str):
        cmd = _wrap_sudo(cmd)
        if 'encoding' in kwargs and kwargs['encoding'] is None:
            inp = (sudo + "\n").encode('utf-8')
        else:
            inp = (sudo + "\n")
        return await asyncio.wait_for(conn.run(cmd, **kwargs, input=inp, check=check), timeout=timeout)
    else:
        return await asyncio.wait_for(conn.run(cmd, **kwargs, check=check), timeout=timeout)


async def run_cmd_logged(lgg: Logger, conn, cmd: str or List[str], sudo=None,
                         timeout: Optional[int] = CMD_TIMEOUT, **kwargs) -> asyncssh.SSHCompletedProcess:
    """
    Helper to run a command on a remote host and log occurred error.

    Instead of possibly raising a ProcessError, we check the result's return code.

    :param lgg: Instance of a logger
    :param conn: Open connection
    :param cmd: The command
    :param sudo: Whether to run command with sudo
    :param timeout: Timeout for this command
    :param kwargs: Passed through to :meth:`asyncssh.SSHClientConnection.run`
    :return: :class:`asyncssh.SSHCompletedProcess`
    """
    r = await run_cmd(conn=conn, cmd=cmd, sudo=sudo, check=False, timeout=timeout, **kwargs)
    if r.returncode != 0:
        lgg.error("Error executing remote command '{}': RETURN CODE={}; STDERR={}".format(
            cmd, r.returncode, r.stderr))
    return r


async def cat_file(lgg: Logger, conn, fn: str, sudo=None, timeout: Optional[int] = CMD_TIMEOUT) \
        -> Optional[List[str]]:
    """
    Cats a file on remote host.

    :param lgg: Instance of a logger
    :param conn: Open connection
    :param fn: Name of the file to cat
    :param sudo: Whether to run command with sudo
    :param timeout: Timeout for this command
    :return: List of strings with file's contents, or None if an error occurred (e.g. file does not exist)
    """
    cmd = ['cat', fn]
    r = await run_cmd(lgg,
                      conn,
                      cmd,
                      sudo=sudo,
                      encoding=None,
                      timeout=timeout)
    if r.returncode != 0:
        return None
    return r.stdout.strip().split("\n")


async def fetch_logs(lgg: Logger, conn, data_dir: str, sudo_pwd=None, timeout: Optional[int] = CMD_TIMEOUT) -> Dict:
    """
    Fetches the log files from remote host.

    The remote files are streamed to a local location. That means,

    - we do not use remote disc space
    - each file is streamed as-is, we do not compress them on the remote side

    :param lgg: Instance of a logger
    :param conn: Open connection
    :param data_dir: Log files are stored in this local directory
    :param sudo_pwd: Password for 'sudo'
    :param timeout: Timeout for this command
    :return: Dict with meta information about the individual fetched log files.
    """

    async def _fetch_meta() -> Dict:
        # TODO factor-out the CMDs so that they can be provided by caller (ff_opspace* need to move out from here).
        cmds = {
            'hostname':          ['hostname'],
            'timeinfo':          ['timedatectl'],
            'ff_syslog':         ['ls', '/var/log/syslog*'],
            'ff_opspace':        ['ls', '/var/log/opspace.*'],
            'ff_opspace_client': ['ls', '/var/log/opspace-client.*'],
            'ff_nginx':          ['ls', '/var/log/nginx/*'],
            'ff_mongodb':        ['ls', '/var/log/mongodb/*'],
        }
        meta = {}
        for k, cmd in cmds.items():
            r = await run_cmd_logged(lgg, conn, cmd, timeout=timeout)
            if r.returncode != 0:
                continue
            else:
                meta[k] = r.stdout.strip().split("\n")
        meta['hostname'] = meta['hostname'][0]
        return meta

    async def _save_json(fn: str, data: Any):
        with open(fn, 'wt', encoding='utf-8') as fp:
            json.dump(data, fp, default=str)

    async def _fetch_logs():
        ff = []
        kk = [k for k in meta.keys() if k.startswith('ff_')]
        for k in kk:
            if meta.get(k):
                ff += meta[k]
        ff.sort()
        lgg.debug(f'Files to fetch: {ff}')
        for f in ff:
            lgg.debug(f"Fetching log '{f}'")
            cmd = ['cat', f]
            file_dir = os.path.join(out_dir, os.path.dirname(f).lstrip(os.path.sep))
            bn = os.path.basename(f)
            os.makedirs(file_dir, exist_ok=True)
            fn = os.path.join(file_dir, bn)
            r = await run_cmd_logged(lgg,
                                     conn,
                                     cmd,
                                     sudo=sudo_pwd,
                                     stdout=fn,
                                     encoding=None,
                                     timeout=timeout)

    meta = await _fetch_meta()
    lgg.debug(f'Meta: {meta}')

    out_dir = os.path.join(data_dir, meta['hostname'])
    os.makedirs(out_dir, exist_ok=True)

    fn = os.path.join(out_dir, 'meta.json')
    await _save_json(fn, meta)
    await _fetch_logs()
    return meta


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


RE_MONGO_NUMBERLONG = re.compile(r'NumberLong\(([-]?\d+)\)')
RE_MONGO_ISODATE = re.compile(r'ISODate\("([^"]+)"\)')
RE_MONGO_OBJECTID = re.compile(r'ObjectId\("([^"]+)"\)')
RE_MONGO_TIMESTAMP = re.compile(r'Timestamp\((\d+,\s+\d+)\)')


def _parse_mongo_json(s: str) -> dict:
    s = RE_MONGO_NUMBERLONG.sub(r'\1', s)
    s = RE_MONGO_ISODATE.sub(r'"\1"', s)
    s = RE_MONGO_OBJECTID.sub(r'"\1"', s)
    s = RE_MONGO_TIMESTAMP.sub(r'[\1]', s)
    return json.loads(s)


async def _run_mongo_command(lgg: Logger, conn, cmd: List[str], sudo: Optional[str] = None,
                             timeout: Optional[int] = CMD_TIMEOUT) -> Optional[Dict]:
    r = await run_cmd_logged(lgg,
                             conn,
                             cmd,
                             sudo=sudo,
                             encoding=None,
                             timeout=timeout)
    if r.returncode != 0:
        return None
    ss = [s for s in r.stdout.decode('utf-8').strip().replace("\t", '  ').split("\n")]
    i = -1
    for i in range(len(ss)):
        if ss[i].startswith('{'):
            break
    if i > -1:
        ss = ss[i:]
    s = "\n".join(ss)
    return _parse_mongo_json(s)


async def fetch_mongo_rs_status(conn, mongo_uri, sudo=None, timeout: Optional[int] = CMD_TIMEOUT) -> Dict:
    """
    Fetches replica set status of MongoDB on remote host.

    :param conn: Open connection
    :param sudo: Password for sudo
    :param timeout: Timeout for this command
    :param mongo_uri: URI to connect to the MongoDB cluster.
    :return: Output of MongoDB's command 'rs.status()'
    """
    lgg = module_logger()
    lgg.debug("Fetching Mongo rs status")
    cmd = ['mongo', mongo_uri, '--quiet', '--eval', '"rs.status()"']
    return await _run_mongo_command(lgg, conn, cmd, sudo, timeout)


async def fetch_mongo_rs_conf(conn, mongo_uri, sudo=None, timeout: Optional[int] = CMD_TIMEOUT) -> Dict:
    """
    Fetches replica set configuration of MongoDB on remote host.

    :param conn: Open connection
    :param sudo: Password for sudo
    :param timeout: Timeout for this command
    :param mongo_uri: URI to connect to the MongoDB cluster.
    :return: Output of MongoDB's command 'rs.status()'
    """
    lgg = module_logger()
    lgg.debug("Fetching Mongo rs conf")
    cmd = ['mongo', mongo_uri, '--quiet', '--eval', '"rs.conf()"']
    return await _run_mongo_command(lgg, conn, cmd, sudo, timeout)


async def fetch_hostname(conn, sudo=None, timeout: Optional[int] = CMD_TIMEOUT) -> str:
    lgg = module_logger()
    lgg.debug('Fetching hostname')
    cmd = ['hostname']
    r = await run_cmd_logged(lgg, conn, cmd, sudo, timeout)
    return r.stdout.strip()
