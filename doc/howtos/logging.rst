.. _logging:

=======
Logging
=======

Python's logging facility is fully initialized with these features

* Log to STDERR
* Log to file with CLI argument `--log-file`
* ISO timestamp
* Process and thread
* Log level can be set on command-line with `--quiet` or `-v[vvv...]`
* Position of log message is logged as filename and line number

Arbitrary data can be logged as serialized JSON by defining property `data` of
the `extra` argument::

    lgg = logging.getLogger()
    lgg.info('My log message', extra={'data': {'some': 'arbitrary data', 'value': 42}})

writes this log output::

    2021-05-16T11:44:31+0200 MainProcess MainThread root         INFO     My log message {"f": "mama/demos/step_2/mama_demo/cmds/hello.py", "l": 23, "data": {"some": "arbitrary data", "value": 42}}


TODO Explain stacking of `-v` beyond DEBUG to set log level for internally used packages like asyncio, urllib3 etc

TODO Explain logging of chained errors

.. seealso::

    * :func:`backinajiffy.mama.cli.set_log_level`
    * :func:`backinajiffy.mama.logging.init_logging` and :const:`backinajiffy.mama.logging.CONFIG_LOGGING`
