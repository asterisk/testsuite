#!/usr/bin/env python
"""Asterisk CSV-based testing

This module implements the basic CSV testing backend for things like
CDR and CEL tests.

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

class AsteriskCSVLine:
    "A single Asterisk call detail record"

    def __init__(self, fields, **kwargs):
        """Construct an Asterisk CSV entry.

        The arguments list definition must be in the same order that the
        arguments appear in the CSV file. They can, of course, be passed to
        __init__ in any order. AsteriskCSV will pass the arguments via a
        **dict.
        """

        # make all arguments passed available as instance variables
        self.__dict__.update(kwargs)
        self.__columns = kwargs
        self.__fields = fields

    def match(self, other, silent=False, exact=(False, False)):
        """Matches if the subset of fields that exist in both records match.

        It is important to make sure that if you want to test against an empty
        field, that it is passed as an empty string and not left out of the
        initialization or passed as None.

        exact - Whether (self, other) contain exact strings (True) or regexes
        """

        if exact == (False, False):
            logger.error("Can't compare two regexes, that's silly")
            return False
        elif exact == (False, True):
            cmp_fn = (lambda x,y: re.match(str(x).lower() + '$', str(y).lower()))
        elif exact == (True, False):
            cmp_fn = (lambda x,y: re.match(str(y).lower() + '$', str(x).lower()))
        else:
            cmp_fn = (lambda x,y: str(x).lower() == str(y).lower())

        for k, v in self.iteritems():
            if None not in (v, other.get(k)):
                if not cmp_fn(v, other.get(k)):
                    if not silent:
                        logger.warn("CSV MATCH FAILED, Expected: %s: '%s' Got: %s: '%s'" % (k, v, k, other.get(k)))
                    return False
        return True

    def get(self, k):
        return self.__columns.get(k)

    def iteritems(self):
        return self.__columns.iteritems()

    def __str__(self):
        return ",".join(["\"%s\"" % (self.__dict__[x]) for x in self.__fields])


class AsteriskCSV:
    """A representation of an Asterisk CSV file"""

    def __init__(self, fn=None, records=None, fields=None, row_factory=None):
        """Initialize CSV records from an Asterisk csv file"""

        self.filename = fn
        self.row_factory = row_factory

        if records:
            self.__records = records
            return

        self.__records = []

        csvreader = None

        try:
            csvreader = csv.DictReader(open(fn, "r"), fields, ",")
        except IOError as (errno, strerror):
            logger.error("IOError %d[%s] while opening file '%s'" % (errno, strerror, fn))
        except:
            logger.error("Unexpected error: %s" % (sys.exc_info()[0]))

        if not csvreader:
            logger.error("Unable to open file '%s'" % (fn))
            return

        for r in csvreader:
            record = self.row_factory(**r)
            self.__records.append(record)

    def __len__(self):
        return len(self.__records)

    def __getitem__(self, key):
        return self.__records.__getitem__(key)

    def __iter__(self):
        return self.__records.__iter__()

    def match(self, other, partial=False):
        """Compares the length of self and other AsteriskCSVs and then compares
        each record"""

        if not partial and (len(self) != len(other)):
            logger.warn("CSV MATCH FAILED, different number of records, self=%d and other=%d" % (len(self), len(other)))
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
            if not partial:
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

        # If there is a filename, then we know that the fields are just text,
        # and not regexes. We need to know this when we are matching individual
        # rows so we know whether it is self or other that has the text we are
        # matching against. If both are file-based, then we know not to use
        # regexes at all and just test equality
        exactness = (bool(self.filename), bool(other.filename))

        # Use the match_order function to see if there either is (a) no match,
        # or (b) a single match or (c) several matches. In the latter case, the
        # regexes should probably be chosen more carefully.
        matches = match_order(self, other, (lambda x, y: x.match(y,
            silent=True, exact=exactness)))

        if len(matches) == 0:
            # Bah.. no match. Loop over the records in the normal order and
            # have it complain immediately.
            for i, x in enumerate(self):
                if not x.match(other[i], exact=exactness):
                    logger.warn("Failed to match entry %d" % (i,))
                    return False
            assert False

        elif len(matches) == 1:
            pass # joy!

        elif len(matches) > 1:
            logger.warn("More than one CSV permutation results in success")

        return True

    def __str__(self):
        return "\n".join([str(x) for x in self.__records])

    def empty(self):
        try:
            open(self.filename, "w").close()
        except:
            logger.warn("Unable to empty CSV file %s" % (self.filename))

if __name__ == '__main__':
    unittest.main()

# vim:sw=4:ts=4:expandtab:textwidth=79
