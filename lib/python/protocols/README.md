## protocols

The "protocols" module provides parsing for PCAP packets
layers 2-4 (Ethernet, IPv4/IPv6, UDP/TCP).  The
Testsuite uses it to parse packets for the tests that
need that functionality.

It was originally part of the
[construct](https://github.com/construct/construct)
module but was removed after v2.5.5.  Unfortunately,
it was and is the only standalone/low overhead packet parsing
module available.

This python package is an extract from the
[construct](https://github.com/construct/construct)
package v2.5.5.  Since construct itself underwent
major API changes since v2.5.5, the protocols
code needed significant work to make it compatible
with the current construct version (2.9 at the
time of this writing).  Since no functional changes
were made, only API compatibility changes, the
original construct (license)[LICENSE.md] still
applies and is included here.

This module is compatible with both python2 and
python3.  It also contains unit tests for every
parser including the top-level ipstack wrapper.
To run the unit tests, you must add
`<testsuite_path>/lib/python` to the `PYTHONPATH`
environment variable.

Example
```
# cd /usr/src/asterisk/testsuite/lib/python
# PYTHONPATH=/usr/src/asterisk/testsuite/lib/python python3
./ipstack.py
```
Or...
```
# cd /usr/src/asterisk/testsuite/lib/python
# PYTHONPATH=../ python3 ./ipstack.py
```

There is also an "unconverted" directory in this
module which contains parsers we don't use and
therefore haven't been updated wo work with
the latest construct.
