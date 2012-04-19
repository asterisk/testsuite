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
import re
import logging
import time

logger = logging.getLogger(__name__)

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
        self.__dict__.update(locals())
        del self.__dict__['self']

    def match(self, other, silent=False):
        """Matches if the subset of fields that exist in both records match.

        It is important to make sure that if you want to test against an empty
        field, that it is passed as an empty string and not left out of the
        initialization or passed as None.
        """

        for k, v in self.iteritems():
            if None not in (v, other.get(k)) and not re.match(
                    "%s$" % (str(v).lower()), str(other.get(k)).lower()):
                if not silent:
                    logger.warn("CDR MATCH FAILED, Expected: %s:%s Got: %s:%s" %
                            (k, v, k, other.get(k)))
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

    def __str__(self):
        return ",".join(["\"%s\"" % (self.__dict__[x]) for x in AsteriskCSVCDRLine.get_fields()])


class AsteriskCSVCDR:
    """A representation of an Asterisk CSV CDR file"""

    def __init__(self, fn=None, records=None):
        """Initialize CDR records from an Asterisk cdr-csv file"""

        self.filename = fn
        if records:
            self.__records = records
            return

        self.__records = []

        cdr = None
        try:
            cdr = csv.DictReader(open(fn, "r"), AsteriskCSVCDRLine.get_fields(), ",")
        except IOError as (errno, strerror):
            logger.debug("IOError %d[%s] while opening CDR file '%s'" % (errno, strerror, fn))
        except:
            logger.debug("Unexpected error: %s" % (sys.exc_info()[0]))

        if not cdr:
            logger.error("Unable to open CDR file '%s'" % (fn))
            return

        for r in cdr:
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
            logger.warn("CDR MATCH FAILED, different number of records")
            return False

        def match_order(list_a, list_b, cmp_func):
            """Utility function that attempts to find out whether list_a and
            list_b have a single ordering match or if there is more than
            one.

            >>> f = (lambda x, y: x == y)
            >>> match_order(['A', 'B', 'C'], ['C', 'B', 'X'], f)
            ()
            >>> match_order(['A', 'B', 'C'], ['C', 'B', 'A'], f)
            ((2, 1, 0),)
            >>> match_order(['A', 'B', 'C', 'B'], ['C', 'B', 'A', 'B'], f)
            ((2, 1, 0, 3), (2, 3, 0, 1))
            """
            assert len(list_a) == len(list_b)
            size = len(list_a)

            # attempt two orderings: forward and reversed
            guess_orders = (range(size), list(reversed(range(size)))) # both mutable
            found_orders = []

            for guess_order in guess_orders:
                found_order = []
                for a in range(size):
                    for b in guess_order:
                        if cmp_func(list_a[a], list_b[b]):
                            found_order.append(b)
                            guess_order.remove(b)
                            break
                    else:
                        # no match at all..
                        return ()
                found_orders.append(tuple(found_order))

            if found_orders[0] != found_orders[1]:
                return tuple(found_orders)
            return (found_orders[0],)

        # Use the match_order function to see if there either is (a) no match,
        # or (b) a single match or (c) several matches. In the latter case, the
        # regexes should probably be chosen more carefully.
        matches = match_order(self, other, (lambda x, y: x.match(y, silent=True)))

        if len(matches) == 0:
            # Bah.. no match. Loop over the records in the normal order and
            # have it complain immediately.
            for i, x in enumerate(self):
                if not x.match(other[i]):
                    return False
            assert False

        elif len(matches) == 1:
            pass # joy!

        elif len(matches) > 1:
            logger.warn("More than one CDR permutation results in success")

        return True

    def __str__(self):
        return "\n".join([str(x) for x in self.__records])

    def empty(self):
        try:
            open(self.filename, "w").close()
        except:
            logger.warn("Unable to empty CDR file %s" % (self.filename))


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
