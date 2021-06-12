import os
import subprocess
from pathlib import Path
from typing import Sequence

INVALID_CHARS = r'<>:"/\|?*' + ''.join([chr(n) for n in range(31)])


def check_filename(f: str, allow_leading_dot=False) -> bool:
    if f.startswith(' ') or f.endswith(' ') or f.endswith('.'):
        return False
    if not allow_leading_dot and f.startswith('.'):
        return False
    for c in INVALID_CHARS:
        if c in f:
            return False
    return True


def sort_filenames(fn: str):
    """
    Sort filenames respecting the number in last or second last segment of basename.

    Use as 'key' in sort function.

    '/var/log/syslog.10.gz',
    '/var/log/syslog.9.gz',
    ...
    '/var/log/syslog.2.gz',
    '/var/log/syslog.1',
    '/var/log/syslog',

    :param fn: Filename
    :return: List of segments where last and second last item is integer, if appropriate
    """
    pp = [os.path.dirname(fn)] + os.path.basename(fn).split('.')
    try:
        pp[-1] = int(pp[-1])
        pp[-1] = str(pp[-1]).zfill(4)
    except ValueError:
        pass
    try:
        pp[-2] = int(pp[-2])
        pp[-2] = str(pp[-2]).zfill(4)
    except ValueError:
        pass
    return pp


def concat_files(ff: Sequence[Path], fn_out: Path):
    fp = open(fn_out, 'wt', encoding='utf-8')
    try:
        for f in ff:
            cmd = ['zcat' if f.name.endswith('.gz') else 'cat', str(f)]
            subprocess.run(cmd, stdout=fp, check=True)
    finally:
        fp.close()
