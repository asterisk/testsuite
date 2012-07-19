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

LOGGER = logging.getLogger(__name__)

class CELModule(object):
    ''' A module that checks a test for expected CEL results '''


    def __init__(self, module_config, test_object):
        ''' Constructor

        Parameters:
        module_config The yaml loaded configuration for the CEL Module
        test_object A concrete implementation of TestClass
        '''
        self.test_object = test_object

        # Build our expected CEL records
        self.cel_records = {}
        for record in module_config:
            file_name = record['file']
            if file_name not in self.cel_records:
                self.cel_records[file_name] = []
            for csv_line in record['lines']:
                # Set the record to the default fields, then update with what
                # was passed in to us
                dict_record = dict((k, None) for k in AsteriskCSVCELLine.fields)
                dict_record.update(csv_line)

                self.cel_records[file_name].append(AsteriskCSVCELLine(**dict_record))

        # Hook ourselves onto the test object
        test_object.register_stop_observer(self._check_cel_records)

    def _check_cel_records(self, callback_param):
        ''' A deferred callback method that is called by the TestCase
        derived object when all Asterisk instances have stopped

        Parameters:
        callback_param
        '''
        LOGGER.debug("Checking CEL records...")
        self.match_cels()
        return callback_param


    def match_cels(self):
        ''' Called when all instances of Asterisk have exited.  Derived
        classes can override this to provide their own behavior for CEL
        matching.
        '''
        expectations_met = True
        for key in self.cel_records:
            cel_expect = AsteriskCSVCEL(records=self.cel_records[key])
            cel_file = AsteriskCSVCEL(fn="%s/%s/cel-custom/%s.csv" %
                (self.test_object.ast[0].base,
                 self.test_object.ast[0].directories['astlogdir'],
                 key))
            if cel_expect.match(cel_file):
                LOGGER.debug("%s.csv - CEL results met expectations" % key)
            else:
                LOGGER.error("%s.csv - CEL results did not meet expectations.  Test Failed." % key)
                expectations_met = False

        self.test_object.set_passed(expectations_met)


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
