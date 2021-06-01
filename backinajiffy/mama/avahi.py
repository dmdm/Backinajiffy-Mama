from typing import Sequence, List, Dict

AVAHI_BROWSE = ['avahi-browse', '-aptr', '--no-db-lookup']
"""Command definition for parseable output of 'avahi-browse'"""
AVAHI_FIELDS = 'kind nic proto name service local hostname addr port'.split()
"""List of avahi fields to parse"""


def parse_output(ss: Sequence[str]) -> List[Dict]:
    """
    Helper to parse output of 'avahi-browse'.

    :param ss: List of strings with raw output
    :return: Parsed output
    """
    dd = []
    for s2 in ss:
        d = {}
        for f in AVAHI_FIELDS:
            try:
                p = s2.index(';')
            except ValueError:
                sf = s2
                d[f] = sf
                break
            else:
                sf = s2[:p]
                s2 = s2[p + 1:]
                d[f] = sf
        dd.append(d)
    return dd
