#!/usr/bin/env python
'''
Copyright (C) 2012, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import logging

sys.path.append("lib/python")
from cdr import CDRModule

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

        if (not self.test_object.passed):
            return

        cdr1 = AsteriskCSVCDR(fn="%s/%s/cdr-csv/%s.csv" %
            (self.test_object.ast[0].base,
             self.test_object.ast[0].directories['astlogdir'], "cdrtest_local"))

        if int(cdr1[0].duration) < int(cdr1[1].duration):
            logger.error("Fail: Original CDR duration shorter than forked")
            self.test_object.passed = False
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

    def match_cdrs(self):
        super(ForkCdrModuleEndTime, self).match_cdrs()

        if (not self.test_object.passed):
            return

        cdr1 = AsteriskCSVCDR(fn = "%s/%s/cdr-csv/%s.csv" %
                (self.test_object.ast[0].base,
                 self.test_object.ast[0].directories['astlogdir'],
                 "cdrtest_local"))

        #check for missing fields
        for cdritem in cdr1:
            if (cdritem.duration is None or
                cdritem.start is None or
                cdritem.end is None):
                logger.Error("EPIC FAILURE: CDR record %s is missing one or " \
                             "more key fields. This should never be able to " \
                             "happen." % cdritem)
                self.test_object.passed = False
                return

        # The dialplan is set up so that these two CDRs should each last at
        # least 4 seconds. Giving it wiggle room, we'll just say we want it to
        # be greater than 1 second.
        if ((int(cdr1[0].duration) <= 1) or (int(cdr1[1].duration) <= 1)):
            logger.error("FAILURE: One or both CDRs only lasted a second or " \
                         "less (expected more)")
            self.test_object.passed = False
            return

        end = time.strptime(cdr1[0].end, "%Y-%m-%d %H:%M:%S")
        beg = time.strptime(cdr1[1].start, "%Y-%m-%d %H:%M:%S")

        #check that the end of the first CDR occured within a 1 second split of
        # the beginning of the second CDR
        if (abs(time.mktime(end) - time.mktime(beg)) > 1):
            logger.error("Time discrepency between end1 and start2 must be " \
                         "one second or less.\n")
            logger.error("Actual times: end cdr1 = %s   begin cdr2 = %s" %
                         (cdr1[0].end, cdr1[1].start))
            self.test_object.passed = False
            return

