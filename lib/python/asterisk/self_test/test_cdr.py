#!/usr/bin/env python
"""Asterisk call detail record unit tests

This module implements an Asterisk CDR parser.

Copyright (C) 2010, Digium, Inc.
Terry Wilson<twilson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

from harness_shared import main
import unittest
from asterisk.cdr import AsteriskCSVCDR, AsteriskCSVCDRLine


class AsteriskCSVCDRTests(unittest.TestCase):
    """Unit tests for AsteriskCSVCDR"""

    def test_cdr(self):
        """Test the self_test/Master.csv record"""

        cdr = AsteriskCSVCDR("lib/python/asterisk/self_test/Master.csv")
        self.assertEqual(len(cdr), 2)
        self.assertTrue(
            AsteriskCSVCDRLine(duration=7, lastapp="hangup").match(
                cdr[0],
                exact=(True, True)))
        self.assertTrue(cdr[0].match(
            AsteriskCSVCDRLine(duration=7, lastapp="hangup"),
            exact=(True, True)))

        self.assertFalse(cdr[1].match(cdr[0], silent=True, exact=(True, True)))
        self.assertFalse(cdr[0].match(cdr[1], silent=True, exact=(True, True)))
        self.assertEqual(cdr[0].billsec, "7")

        self.assertTrue(cdr.match(cdr))
        cdr2 = AsteriskCSVCDR("lib/python/asterisk/self_test/Master2.csv")
        self.assertFalse(cdr.match(cdr2))


if __name__ == '__main__':
    main()
