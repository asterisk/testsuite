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

from collections import defaultdict

LOGGER = logging.getLogger(__name__)

class CDRModule(object):
    ''' A module that checks a test for expected CDR results '''


    def __init__(self, module_config, test_object):
        ''' Constructor

        Parameters:
        module_config The yaml loaded configuration for the CDR Module
        test_object A concrete implementation of TestClass
        '''
        self.test_object = test_object

        # Build our expected CDR records
        self.cdr_records = {}
        for record in module_config:
            file_name = record['file']
            if file_name not in self.cdr_records:
                self.cdr_records[file_name] = []
            for csv_line in record['lines']:
                # Set the record to the default fields, then update with what
                # was passed in to us
                dict_record = dict((k, None) for k in AsteriskCSVCDRLine.fields)
                dict_record.update(csv_line)

                self.cdr_records[file_name].append(AsteriskCSVCDRLine(
                    accountcode=dict_record['accountcode'], source=dict_record['source'],
                    destination=dict_record['destination'], dcontext=dict_record['dcontext'],
                    callerid=dict_record['callerid'], channel=dict_record['channel'],
                    dchannel=dict_record['dchannel'], lastapp=dict_record['lastapp'],
                    lastarg=dict_record['lastarg'], start=dict_record['start'],
                    answer=dict_record['answer'], end=dict_record['end'],
                    duration=dict_record['duration'], billsec=dict_record['billsec'],
                    disposition=dict_record['disposition'], amaflags=dict_record['amaflags'],
                    uniqueid=dict_record['uniqueid'], userfield=dict_record['userfield']))

        # Hook ourselves onto the test object
        test_object.register_stop_observer(self._check_cdr_records)

    def _check_cdr_records(self, callback_param):
        ''' A deferred callback method that is called by the TestCase
        derived object when all Asterisk instances have stopped

        Parameters:
        callback_param
        '''
        LOGGER.debug("Checking CDR records...")
        self.match_cdrs()
        return callback_param


    def match_cdrs(self):
        ''' Called when all instances of Asterisk have exited.  Derived
        classes can override this to provide their own behavior for CDR
        matching.
        '''
        expectations_met = True
        for key in self.cdr_records:
            cdr_expect = AsteriskCSVCDR(records=self.cdr_records[key])
            cdr_file = AsteriskCSVCDR(fn="%s/%s/cdr-csv/%s.csv" %
                (self.test_object.ast[0].base,
                 self.test_object.ast[0].directories['astlogdir'],
                 key))
            if cdr_expect.match(cdr_file):
                LOGGER.debug("%s.csv - CDR results met expectations" % key)
            else:
                LOGGER.error("%s.csv - CDR results did not meet expectations.  Test Failed." % key)
                expectations_met = False

        self.test_object.passed = expectations_met


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
