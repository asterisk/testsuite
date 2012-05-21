#!/usr/bin/env python
"""Asterisk call detail record testing

This module implements an Asterisk CEL parser.

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

class AsteriskCSVCELLine(astcsv.AsteriskCSVLine):
    "A single Asterisk Call Event Log record"

    fields = ['eventtype', 'eventtime', 'cidname', 'cidnum', 'ani', 'rdnis',
    'dnid', 'exten', 'context', 'channel', 'app', 'appdata', 'amaflags',
    'accountcode', 'uniqueid', 'linkedid', 'bridgepeer', 'userfield',
    'userdeftype', 'eventextra']

    def __init__(self, eventtype=None, eventtime=None, cidname=None, cidnum=None,
    ani=None, rdnis=None, dnid=None, exten=None, context=None, channel=None,
    app=None, appdata=None, amaflags=None, accountcode=None, uniqueid=None,
    linkedid=None, bridgepeer=None, userfield=None, userdeftype=None,
    eventextra=None):
        """Construct an Asterisk CSV CEL.

        The arguments list definition must be in the same order that the
        arguments appear in the CSV file. They can, of course, be passed to
        __init__ in any order. AsteriskCSVCEL will pass the arguments via a
        **dict.
        """

        return astcsv.AsteriskCSVLine.__init__(self, AsteriskCSVCELLine.fields,
        eventtype=eventtype, eventtime=eventtime, cidname=cidname,
        cidnum=cidnum, ani=ani, rdnis=rdnis, dnid=dnid, exten=exten,
        context=context, channel=channel, app=app, appdata=appdata,
        amaflags=amaflags, accountcode=accountcode, uniqueid=uniqueid,
        linkedid=linkedid, bridgepeer=bridgepeer, userfield=userfield,
        userdeftype=userdeftype, eventextra=eventextra)

class AsteriskCSVCEL(astcsv.AsteriskCSV):
    """A representation of an Asterisk CSV CEL file"""

    def __init__(self, fn=None, records=None):
        """Initialize CEL records from an Asterisk cel-csv file"""

        return astcsv.AsteriskCSV.__init__(self, fn, records,
                AsteriskCSVCELLine.fields, AsteriskCSVCELLine)


class AsteriskCSVCELTests(unittest.TestCase):
    def test_cel(self):
        c = AsteriskCSVCEL("self_test/CELMaster1.csv")
        self.assertEqual(len(c), 16)
        self.assertTrue(AsteriskCSVCELLine(eventtype="LINKEDID_END",channel="TinCan/string").match(c[-1],
            silent=True, exact=(True, True)))
        self.assertTrue(c[-1].match(AsteriskCSVCELLine(eventtype="LINKEDID_END",channel="TinCan/string"),
            silent=True, exact=(True, True)))

        self.assertFalse(c[1].match(c[0], silent=True))
        self.assertFalse(c[0].match(c[1], silent=True))
        self.assertEqual(c[-1].channel, "TinCan/string")

        self.assertTrue(c.match(c))
        c2 = AsteriskCSVCEL("self_test/CELMaster2.csv")
        self.assertFalse(c.match(c2))


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
