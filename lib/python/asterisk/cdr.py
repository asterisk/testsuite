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

class AsteriskCSVCDRLine:
    "A single Asterisk call detail record"

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

        # make all arguments passed available as instance variables
        tmp = locals()
        del tmp['self']
        self.__dict__.update(tmp)

    def match(self, other):
        """Matches if the subset of fields that exist in both records match.

        It is important to make sure that if you want to test against an empty
        field, that it is passed as an empty string and not left out of the
        initialization or passed as None.
        """

        for k,v in self.iteritems():
            if None not in (v, other.get(k)) and str(v).lower() != str(other.get(k)).lower():
                print "CDR MATCH FAILED, Expected: %s:%s Got: %s:%s" % (k, v,
                        k, other.get(k))
                return False
        return True

    def get(self, k):
        return self.__dict__.get(k)

    def iteritems(self):
        return self.__dict__.iteritems()

    __fields = __init__.func_code.co_varnames[1:]

    @classmethod
    def get_fields(self):
        return self.__fields

    @classmethod
    def get_field(self, i):
        return self.__fields[i]


class AsteriskCSVCDR:
    """A representation of an Asterisk CSV CDR file"""

    def __init__(self, fn=None, records=None):
        """Initialize CDR records from an Asterisk cdr-csv file"""

        if records:
            self.__records = records
            return

        self.__records = []
        try:
            f = open(fn, "r")
            lines = f.read().splitlines()
            f.close()
        except IOError:
            print "Failed to open CDR file '%s'" %s (fn)
            return
        except:
            print "Unexpected error: %s" % (sys.exc_info()[0])
            return

        for line in lines:
            r = dict([(AsteriskCSVCDRLine.get_field(i), x.strip('"')) for i,x in enumerate(line.split(','))])
            record = AsteriskCSVCDRLine(**r)
            self.__records.append(record)

    def __len__(self):
        return len(self.__records)

    def __getitem__(self, key):
        return self.__records.__getitem__(key)

    def __iter__(self):
        return self.__records.__iter__()

    def match(self, other):
        """Compares the length of self and other AsteriskCSVCDRs and then compares
        each record"""

        if len(self) != len(other):
            print "CDR MATCH FAILED, different number of records"
            return False
        for i,x in enumerate(self):
            if not x.match(other[i]):
                return False
        return True


class AsteriskCSVCDRTests(unittest.TestCase):
    def test_cdr(self):
        c = AsteriskCSVCDR("self_test/Master.csv")
        self.assertEqual(len(c), 2)
        self.assertTrue(AsteriskCSVCDRLine(duration=7,lastapp="hangup").match(c[0]))
        self.assertTrue(c[0].match(AsteriskCSVCDRLine(duration=7,lastapp="hangup")))

        self.assertFalse(c[1].match(c[0]))
        self.assertFalse(c[0].match(c[1]))
        self.assertEqual(c[0].billsec, "7")

        self.assertTrue(c.match(c))
        c2 = AsteriskCSVCDR("self_test/Master2.csv")
        self.assertFalse(c.match(c2))


if __name__ == '__main__':
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
