#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)


class DestroyTest(object):
    def __init__(self, rt_data, test_object, ami):
        self.rt_data = rt_data
        self.test_object = test_object
        self.ami = ami

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def pass_test(self):
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def mwi_callback(self, ami, event):
        LOGGER.debug("Received MWI event %s" % event)

        event_mailbox = event.get('mailbox')

        query = dict(id=event_mailbox)
        rt_row = self.rt_data.retrieve_row('mwi', query)
        if rt_row:
            LOGGER.error("Mailbox %s in AMI event still exists in realtime" %
                         event_mailbox)
            self.fail_test()

        self.pass_test()


def check_it(rt_data, test_object, ami):
    test = DestroyTest(rt_data, test_object, ami)

    ami.registerEvent('MessageWaiting', test.mwi_callback)
    message = {
        'Action': 'MWIDelete',
        'Mailbox': 'Dazed',
    }
    ami.sendMessage(message)
