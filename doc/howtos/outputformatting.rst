.. _outputformatting:

=================
Output Formatting
=================

By default, Mama uses Python's print method to, well, print your output. Unless it thinks your data could be
tabular::

    data = [
            {'some': 'arbitrary data', 'value': 42},
            {'some': 'more data', 'value': 84}
        ]

then the output looks like this::

        some        value
    --------------  -------
    arbitrary data       42
    more data            84

You can output your data in JSON, YAML, or even pretty-print it with CLI argument `-F/--output-format`::

    # -F json
    [{"some":"arbitrary data","value":42},{"some":"more data","value":84}]

    # -F yaml
    - some: arbitrary data
      value: 42
    - some: more data
      value: 84

    # -F ptxt     # it's not JSON! Look at the quotation marks.
    [{'some': 'arbitrary data', 'value': 42}, {'some': 'more data', 'value': 84}]


Custom Formatting
=================

If you need to format your output yourself, override method :meth:`backinajiffy.mama.cli.BaseCmd.format_data`, e.g.::

    class MyCommand:
        # ...
        def format_data(data: Any) -> s:
            buf = io.StringIO()
            print(..., file=buf)
            print(..., file=buf)
            ...
            s = buf.getvalue()
            buf.close()
            return s
