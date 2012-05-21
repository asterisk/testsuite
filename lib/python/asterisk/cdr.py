#!/usr/bin/env python
"""Asterisk call detail record testing

This module implements an Asterisk CDR parser.

Copyright (C) 2010, Digium, Inc.
Terry Wilson<twilson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import unittest
import sys
import csv
import astcsv
import re
import logging
import time

logger = logging.getLogger(__name__)

class AsteriskCSVCDRLine(astcsv.AsteriskCSVLine):
    "A single Asterisk call detail record"

    fields = ['accountcode', 'source', 'destination', 'dcontext', 'callerid',
    'channel', 'dchannel', 'lastapp', 'lastarg', 'start', 'answer', 'end',
    'duration', 'billsec', 'disposition', 'amaflags', 'uniqueid', 'userfield']

    def __init__(self, accountcode=None, source=None, destination=None,
            dcontext=None, callerid=None, channel=None, dchannel=None,
            lastapp=None, lastarg=None, start=None, answer=None, end=None,
            duration=None, billsec=None, disposition=None, amaflags=None,
            uniqueid=None, userfield=None):
        """Construct an Asterisk CSV CDR.

        The arguments list definition must be in the same order that the
        arguments appear in the CSV file. They can, of course, be passed to
        __init__ in any order. AsteriskCSVCDR will pass the arguments via a
        **dict.
        """

        return astcsv.AsteriskCSVLine.__init__(self,
            AsteriskCSVCDRLine.fields, accountcode=accountcode,
            source=source, destination=destination,
            dcontext=dcontext, callerid=callerid, channel=channel,
            dchannel=dchannel, lastapp=lastapp, lastarg=lastarg, start=start, answer=answer,
            end=end, duration=duration, billsec=billsec, disposition=disposition,
            amaflags=amaflags, uniqueid=uniqueid, userfield=userfield)


class AsteriskCSVCDR(astcsv.AsteriskCSV):
    """A representation of an Asterisk CSV CDR file"""

    def __init__(self, fn=None, records=None):
        """Initialize CDR records from an Asterisk cdr-csv file"""

        return astcsv.AsteriskCSV.__init__(self, fn, records,
                AsteriskCSVCDRLine.fields, AsteriskCSVCDRLine)


class AsteriskCSVCDRTests(unittest.TestCase):
    def test_cdr(self):
        c = AsteriskCSVCDR("self_test/Master.csv")
        self.assertEqual(len(c), 2)
        self.assertTrue(AsteriskCSVCDRLine(duration=7,lastapp="hangup").match(c[0],
            exact=(True, True)))
        self.assertTrue(c[0].match(AsteriskCSVCDRLine(duration=7,lastapp="hangup"),
            exact=(True, True)))

        self.assertFalse(c[1].match(c[0]))
        self.assertFalse(c[0].match(c[1]))
        self.assertEqual(c[0].billsec, "7")

        self.assertTrue(c.match(c))
        c2 = AsteriskCSVCDR("self_test/Master2.csv")
        self.assertFalse(c.match(c2))


if __name__ == '__main__':
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
