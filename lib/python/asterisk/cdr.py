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
import astcsv
import logging

LOGGER = logging.getLogger(__name__)


class CDRModule(object):
    """A module that checks a test for expected CDR results"""

    def __init__(self, module_config, test_object):
        """Constructor

        Parameters:
        module_config The yaml loaded configuration for the CDR Module
        test_object A concrete implementation of TestClass
        """
        self.test_object = test_object

        # Build our expected CDR records
        self.cdr_records = {}
        for record in module_config:
            file_name = record['file']
            ast_id = record.get('id') or 0
            if ast_id not in self.cdr_records:
                self.cdr_records[ast_id] = {}
            if file_name not in self.cdr_records[ast_id]:
                self.cdr_records[ast_id][file_name] = []
            for csv_line in record['lines']:
                # Set the record to the default fields, then update with what
                # was passed in to us
                dict_record = dict((k, None) for k in AsteriskCSVCDRLine.fields)
                if csv_line is not None:
                    dict_record.update(csv_line)

                self.cdr_records[ast_id][file_name].append(
                    AsteriskCSVCDRLine(**dict_record))

        # Hook ourselves onto the test object
        test_object.register_stop_observer(self._check_cdr_records)

    def _check_cdr_records(self, callback_param):
        """A deferred callback method that is called by the TestCase
        derived object when all Asterisk instances have stopped

        Parameters:
        callback_param
        """
        LOGGER.debug("Checking CDR records...")
        try:
            self.match_cdrs()
        except:
            LOGGER.error("Exception while checking CDRs: %s" %
                         sys.exc_info()[0])
        return callback_param

    def match_cdrs(self):
        """Called when all instances of Asterisk have exited.  Derived
        classes can override this to provide their own behavior for CDR
        matching.
        """
        expectations_met = True
        for ast_id in self.cdr_records:
            ast_instance = self.test_object.ast[ast_id]
            for file_name in self.cdr_records[ast_id]:
                records = self.cdr_records[ast_id][file_name]
                cdr_expect = AsteriskCSVCDR(records=records)
                cdr_file = AsteriskCSVCDR(filename=ast_instance.get_path(
                    "astlogdir", "cdr-csv", "%s.csv" % file_name))
                if cdr_expect.match(cdr_file):
                    LOGGER.debug("%s.csv: CDR results met expectations" %
                                 file_name)
                else:
                    LOGGER.error("%s.csv: actual did not match expected." %
                                 file_name)
                    expectations_met = False

        self.test_object.set_passed(expectations_met)


class AsteriskCSVCDRLine(astcsv.AsteriskCSVLine):
    """A single Asterisk call detail record"""

    fields = [
        'accountcode', 'source', 'destination', 'dcontext', 'callerid',
        'channel', 'dchannel', 'lastapp', 'lastarg', 'start', 'answer', 'end',
        'duration', 'billsec', 'disposition', 'amaflags', 'uniqueid', 'userfield']

    def __init__(
            self, accountcode=None, source=None, destination=None,
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

        astcsv.AsteriskCSVLine.__init__(
            self, AsteriskCSVCDRLine.fields, accountcode=accountcode,
            source=source, destination=destination,
            dcontext=dcontext, callerid=callerid, channel=channel,
            dchannel=dchannel, lastapp=lastapp, lastarg=lastarg, start=start,
            answer=answer, end=end, duration=duration, billsec=billsec,
            disposition=disposition, amaflags=amaflags, uniqueid=uniqueid,
            userfield=userfield)


class AsteriskCSVCDR(astcsv.AsteriskCSV):
    """A representation of an Asterisk CSV CDR file"""

    def __init__(self, filename=None, records=None):
        """Initialize CDR records from an Asterisk cdr-csv file"""

        astcsv.AsteriskCSV.__init__(
            self, filename, records,
            AsteriskCSVCDRLine.fields, AsteriskCSVCDRLine)


class AsteriskCSVCDRTests(unittest.TestCase):
    """Unit tests for AsteriskCSVCDR"""

    def test_cdr(self):
        """Test the self_test/Master.csv record"""

        cdr = AsteriskCSVCDR("self_test/Master.csv")
        self.assertEqual(len(cdr), 2)
        self.assertTrue(
            AsteriskCSVCDRLine(duration=7, lastapp="hangup").match(
                cdr[0],
                exact=(True, True)))
        self.assertTrue(cdr[0].match(
            AsteriskCSVCDRLine(duration=7, lastapp="hangup"),
            exact=(True, True)))

        self.assertFalse(cdr[1].match(cdr[0]))
        self.assertFalse(cdr[0].match(cdr[1]))
        self.assertEqual(cdr[0].billsec, "7")

        self.assertTrue(cdr.match(cdr))
        cdr2 = AsteriskCSVCDR("self_test/Master2.csv")
        self.assertFalse(cdr.match(cdr2))


if __name__ == '__main__':
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
