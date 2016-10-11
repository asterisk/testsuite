#!/usr/bin/env python
"""Asterisk call detail record testing

This module implements an Asterisk CEL parser.

Copyright (C) 2010, Digium, Inc.
Terry Wilson<twilson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import yaml
import unittest
from . import astcsv
import re
import logging

LOGGER = logging.getLogger(__name__)


class CELSniffer(object):
    """A pluggable module that sniffs AMI CEL events and dumps them into a YAML
    file. Useful during test writing to create a baseline of expected CEL events
    """

    def __init__(self, module_config, test_object):
        """Constructor"""
        test_object.register_ami_observer(self.ami_connect)
        test_object.register_stop_observer(self.stop_handler)
        self.events = []
        if module_config is None:
            self.filters = {}
            self.display = []
        else:
            self.filters = module_config.get('filters') or {}
            self.display = module_config.get('display') or []

    def ami_connect(self, ami):
        """AMI connection handler"""
        ami.registerEvent('CEL', self.cel_handler)

    def cel_handler(self, ami, event):
        """Handle a CEL event"""
        for filter_key, filter_value in self.filters.items():
            if re.match(filter_value, event.get(filter_key.lower())) is None:
                return
        self.events.append(event)
        return (ami, event)

    def stop_handler(self, reason):
        """Write out the file. Currently hard codd to cel_events.yaml"""
        stream = open('cel_events.yaml', 'w')
        if len(self.display) == 0:
            yaml.dump(self.events, stream)
        else:
            items = []
            for ev_item in self.events:
                item = {}
                for key in self.display:
                    key = key.lower()
                    if key not in ev_item:
                        continue
                    item[key] = ev_item[key]
                items.append(item)
            yaml.dump(items, stream)
        stream.close()

        return reason


class CELModule(object):
    """Class that checks a test for expected CEL results"""

    def __init__(self, module_config, test_object):
        """Constructor

        Parameters:
        module_config The yaml loaded configuration for the CEL Module
        test_object A concrete implementation of TestClass
        """
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
                if csv_line is not None:
                    dict_record.update(csv_line)

                file_records = self.cel_records[file_name]
                file_records.append(AsteriskCSVCELLine(**dict_record))

        # Hook ourselves onto the test object
        test_object.register_stop_observer(self._check_cel_records)

    def _check_cel_records(self, callback_param):
        """A deferred callback method that is called by the TestCase
        derived object when all Asterisk instances have stopped

        Parameters:
        callback_param
        """
        LOGGER.debug("Checking CEL records...")
        self.match_cels()
        return callback_param

    def match_cels(self):
        """Called when all instances of Asterisk have exited.  Derived
        classes can override this to provide their own behavior for CEL
        matching.
        """
        expectations_met = True
        for key in self.cel_records:
            cel_expect = AsteriskCSVCEL(records=self.cel_records[key])
            cel_file = AsteriskCSVCEL(filename=self.test_object.ast[0].get_path(
                "astlogdir", "cel-custom", "%s.csv" % key))
            if cel_expect.match(cel_file):
                LOGGER.debug("%s.csv - CEL results met expectations" % key)
            else:
                msg = ("%s.csv - CEL results did not meet expectations. "
                       "Test Failed." % key)
                LOGGER.error(msg)
                expectations_met = False

        self.test_object.set_passed(expectations_met)


class AsteriskCSVCELLine(astcsv.AsteriskCSVLine):
    "A single Asterisk Call Event Log record"

    fields = [
        'eventtype', 'eventtime', 'cidname', 'cidnum', 'ani', 'rdnis',
        'dnid', 'exten', 'context', 'channel', 'app', 'appdata', 'amaflags',
        'accountcode', 'uniqueid', 'linkedid', 'bridgepeer', 'userfield',
        'userdeftype', 'eventextra']

    def __init__(
            self, eventtype=None, eventtime=None, cidname=None,
            cidnum=None, ani=None, rdnis=None, dnid=None, exten=None,
            context=None, channel=None, app=None, appdata=None,
            amaflags=None, accountcode=None, uniqueid=None, linkedid=None,
            bridgepeer=None, userfield=None, userdeftype=None,
            eventextra=None):
        """Construct an Asterisk CSV CEL.

        The arguments list definition must be in the same order that the
        arguments appear in the CSV file. They can, of course, be passed to
        __init__ in any order. AsteriskCSVCEL will pass the arguments via a
        **dict.
        """

        astcsv.AsteriskCSVLine.__init__(
            self, AsteriskCSVCELLine.fields,
            eventtype=eventtype, eventtime=eventtime, cidname=cidname,
            cidnum=cidnum, ani=ani, rdnis=rdnis, dnid=dnid, exten=exten,
            context=context, channel=channel, app=app, appdata=appdata,
            amaflags=amaflags, accountcode=accountcode, uniqueid=uniqueid,
            linkedid=linkedid, bridgepeer=bridgepeer, userfield=userfield,
            userdeftype=userdeftype, eventextra=eventextra)


class AsteriskCSVCEL(astcsv.AsteriskCSV):
    """A representation of an Asterisk CSV CEL file"""

    def __init__(self, filename=None, records=None):
        """Initialize CEL records from an Asterisk cel-csv file"""

        astcsv.AsteriskCSV.__init__(
            self, filename, records,
            AsteriskCSVCELLine.fields, AsteriskCSVCELLine)


class AsteriskCSVCELTests(unittest.TestCase):
    """Unit tests for AsteriskCSVCEL"""

    def test_cel(self):
        """Test CEL using self_test/CELMaster1.csv"""

        cel = AsteriskCSVCEL("self_test/CELMaster1.csv")
        self.assertEqual(len(cel), 16)
        self.assertTrue(AsteriskCSVCELLine(
            eventtype="LINKEDID_END",
            channel="TinCan/string").match(cel[-1],
                                           silent=True,
                                           exact=(True, True)))
        self.assertTrue(cel[-1].match(
            AsteriskCSVCELLine(eventtype="LINKEDID_END",
                               channel="TinCan/string"),
            silent=True,
            exact=(True, True)))

        self.assertFalse(cel[1].match(cel[0], silent=True))
        self.assertFalse(cel[0].match(cel[1], silent=True))
        self.assertEqual(cel[-1].channel, "TinCan/string")

        self.assertTrue(cel.match(cel))
        cel2 = AsteriskCSVCEL("self_test/CELMaster2.csv")
        self.assertFalse(cel.match(cel2))


if __name__ == '__main__':
    logging.basicConfig()
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
