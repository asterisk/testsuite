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
from asterisk.cel import AsteriskCSVCEL, AsteriskCSVCELLine


class AsteriskCSVCELTests(unittest.TestCase):
    """Unit tests for AsteriskCSVCEL"""

    def test_cel(self):
        """Test CEL using self_test/CELMaster1.csv"""

        cel = AsteriskCSVCEL("lib/python/asterisk/self_test/CELMaster1.csv")
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

        self.assertFalse(cel[1].match(cel[0], silent=True, exact=(True, True)))
        self.assertFalse(cel[0].match(cel[1], silent=True, exact=(True, True)))
        self.assertEqual(cel[-1].channel, "TinCan/string")

        self.assertTrue(cel.match(cel))
        cel2 = AsteriskCSVCEL("lib/python/asterisk/self_test/CELMaster2.csv")
        self.assertFalse(cel.match(cel2))


if __name__ == '__main__':
    main()
