from datetime import datetime, tzinfo


def add_default_tz(x: datetime, atzinfo: tzinfo) -> datetime:
    return x.replace(tzinfo=x.tzinfo or atzinfo)
