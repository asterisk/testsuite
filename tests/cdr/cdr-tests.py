#!/usr/bin/env python
''' Pluggable modules for Asterisk CDR tests

Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")
from cdr import CDRModule
from cdr import AsteriskCSVCDR

logger = logging.getLogger(__name__)

class ForkCdrModuleBasic(CDRModule):
    ''' A class that adds some additional CDR checking on top of CDRModule

    In addition to checking the normal expectations, this class also checks
    that the original CDRs duration is not shorter then the forked CDR duration.

    Note that this class assumes the CDRs are in cdrtest_local.
    '''

    def __init__(self, module_config, test_object):
        super(ForkCdrModuleBasic, self).__init__(module_config, test_object)

    def match_cdrs(self):
        super(ForkCdrModuleBasic, self).match_cdrs()

        cdr1 = AsteriskCSVCDR(fn="%s/%s/cdr-csv/%s.csv" %
            (self.test_object.ast[0].base,
             self.test_object.ast[0].directories['astlogdir'], "cdrtest_local"))

        if int(cdr1[0].duration) < int(cdr1[1].duration):
            logger.error("Fail: Original CDR duration shorter than forked")
            self.test_object.set_passed(False)
        return


class ForkCdrModuleEndTime(CDRModule):
    ''' A class that adds some additional CDR checking of the end times on top
    of CDRModule

    In addition to checking the normal expectations, this class also checks
    whether or not the end times of the CDRs are within some period of time
    of each each other.

    Note that this class assumes the CDRs are in cdrtest_local.
    '''

    def __init__(self, module_config, test_object):
        super(ForkCdrModuleEndTime, self).__init__(module_config, test_object)
        self.entries_to_check = module_config[0]['check-entries']

    def match_cdrs(self):
        super(ForkCdrModuleEndTime, self).match_cdrs()

        cdr1 = AsteriskCSVCDR(fn = "%s/%s/cdr-csv/%s.csv" %
                (self.test_object.ast[0].base,
                 self.test_object.ast[0].directories['astlogdir'],
                 "cdrtest_local"))

        logger.debug('Checking for missing fields')
        for cdritem in cdr1:
            if (cdritem.duration is None or
                cdritem.start is None or
                cdritem.end is None):
                logger.error("EPIC FAILURE: CDR record %s is missing one or " \
                             "more key fields. This should never be able to " \
                             "happen." % cdritem)
                self.test_object.set_passed(False)
                return

        # The dialplan is set up so that these two CDRs should each last at
        # least 4 seconds. Giving it wiggle room, we'll just say we want it to
        # be greater than 1 second.
        logger.debug('Checking durations')
        for entry in self.entries_to_check:
            if (int(cdr1[entry].duration) <= 1):
                logger.error("CDR at %d has duration less than one second" %
                             entry)
                self.test_object.set_passed(False)
                return

        logger.debug('Checking start/end times for forked entries')
        for i in range(len(self.entries_to_check) - 1):
            end = time.strptime(cdr1[self.entries_to_check[i]].end, "%Y-%m-%d %H:%M:%S")
            beg = time.strptime(cdr1[self.entries_to_check[i + 1]].start, "%Y-%m-%d %H:%M:%S")

            #check that the end of the first CDR occurred within 1 second of
            # the beginning of the second CDR
            if (abs(time.mktime(end) - time.mktime(beg)) > 1):
                logger.error("Time discrepancy between end1 and start2: must " \
                             "be one second or less.\n")
                logger.error("Actual times: end cdr1 = %s   begin cdr2 = %s" %
                             (cdr1[self.entries_to_check[i]].end,
                              cdr1[self_entries_to_check[i + 1]].start))
                self.test_object.set_passed(False)
                return

        self.test_object.set_passed(True)

