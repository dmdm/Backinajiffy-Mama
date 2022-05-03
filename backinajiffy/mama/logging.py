import json
import logging
import logging.config
import logging.handlers
from copy import deepcopy
from typing import Optional, List

# NB: ConvertingList, ConvertingDict, valid_ident are undocumented and will create errors in PyCharm.
#     Told PyCharm to ignore these.
from logging.config import ConvertingList, ConvertingDict, valid_ident
from logging.handlers import QueueHandler, QueueListener
import atexit


def _resolve_handlers(l):
    if not isinstance(l, ConvertingList):
        return l

    # Indexing the list performs the evaluation.
    return [l[i] for i in range(len(l))]


def _resolve_queue(q):
    if not isinstance(q, ConvertingDict):
        return q
    if '__resolved_value__' in q:
        return q['__resolved_value__']

    cname = q.pop('class')
    klass = q.configurator.resolve(cname)
    props = q.pop('.', None)
    kwargs = {k: q[k] for k in q if valid_ident(k)}
    result = klass(**kwargs)
    if props:
        for name, value in props.items():
            setattr(result, name, value)

    q['__resolved_value__'] = result
    return result


# Cf https://medium.com/@rob.blackbourn/how-to-use-python-logging-queuehandler-with-dictconfig-1e8b1284e27a
class QueueListenerHandler(QueueHandler):

    def __init__(self, handlers, queue, respect_handler_level=False, auto_run=True):
        queue = _resolve_queue(queue)
        super().__init__(queue)
        handlers = _resolve_handlers(handlers)
        self._listener = QueueListener(
            self.queue,
            *handlers,
            respect_handler_level=respect_handler_level)
        if auto_run:
            self.start()
            atexit.register(self.stop)

    def start(self):
        self._listener.start()

    def stop(self):
        self._listener.stop()

    def emit(self, record):
        return super().emit(record)


class MamaFormatter(logging.Formatter):
    """
    Custom log formatter

    Features:

    - Formats stack trace to be on one line
    - Appends JSON object with additional data:

      - Location where logger was called is provided as properties "f" (file name) and "l" (line number)
      - Extra data can be included by calling a log method with argument 'extra'. This data will be provided
        as property "data"::

            lgg.info('My message', extra={'data': {'x': 5, 'marker': 'list-sources'}}
    """

    def formatException(self, exc_info):
        """
        Format an exception so that it prints on a single line.
        """
        result = super().formatException(exc_info)
        return repr(result)  # or format into one line however you want to

    def format(self, record):
        s = super().format(record)
        xtra = {
            'f': record.pathname,
            'l': record.lineno
        }
        if hasattr(record, 'data'):
            xtra['data'] = record.data
        s += ' ' + json.dumps(xtra, default=str)
        if record.exc_text:
            s = s.replace('\n', '')
        return s


CONFIG_LOGGING = {
    'version':                  1,
    'objects':                  {
        'queue': {
            'class':   'multiprocessing.Queue',
            'maxsize': -1
        }
    },
    'disable_existing_loggers': False,
    'formatters':               {
        'tz': {
            '()':      'backinajiffy.mama.logging.MamaFormatter',
            'format':  '%(asctime)s %(processName)s %(threadName)s %(name)-12s %(levelname)-8s %(message)s',
            'datefmt': '%Y-%m-%dT%H:%M:%S%z'
        },
    },
    'handlers':                 {
        'console':        {
            'class':     'logging.StreamHandler',
            'stream':    'ext://sys.stderr',
            'formatter': 'tz',
        },
        'file':           {
            'class':     'logging.FileHandler',
            'formatter': 'tz',
            'filename':  '/tmp/mama.log'  # Override this in init_logging()
        },
        'queue_listener': {
            'class':    'backinajiffy.mama.logging.QueueListenerHandler',
            # append a file handler in init_logging() when args.log-file is given
            'handlers': ['cfg://handlers.console'],
            'queue':    'cfg://objects.queue',
            'auto_run': True
        }
    },
    'root':                     {
        'handlers': ['console'],
    },
    'loggers':                  {
        'paramiko':     {
            'level': 'INFO'
        },
        'asyncio':      {
            'level': 'INFO'
        },
        'aiohttp':      {
            'level': 'INFO'
        },
        'asyncssh':     {
            'level': 'WARNING'
        },
        'mama':         {
            'level': 'INFO'
        },
        'backinajiffy': {
            'level': 'DEBUG'
        }
    }
}
"""Default logging configuration."""


def init_logging(log_file: Optional[str] = None, config_dict=None):
    """
    Initializes Python's logging infrastructure.

    :param log_file:
    :param config_dict: Dict with the logging configuration. By default :const:`CONFIG_LOGGING`.
    """
    if not config_dict:
        config_dict = CONFIG_LOGGING
    conf = deepcopy(config_dict)
    if log_file:
        conf['handlers']['file']['filename'] = log_file
        conf['handlers']['queue_listener']['handlers'].append('cfg://handlers.file')
    logging.config.dictConfig(conf)


def get_error_msg_chain(exc: BaseException, msgs: Optional[List[str]] = None, sep=' ⇠ ') -> str:
    """
    Formats a chain of exceptions as a single-line string.

    A chain of exceptions can be created e.g. with::

        except SomeException as e:
            raise OtherException('Foo') from e

    :param exc: The exception to format
    :param msgs: Optional preceding messages
    :param sep: Concatenates messages with this separator
    :return: The formatted string
    """
    if msgs is None:
        msgs = []
    msgs.append(str(exc))
    if exc.__cause__:
        get_error_msg_chain(exc.__cause__, msgs)
    return sep.join(msgs)
