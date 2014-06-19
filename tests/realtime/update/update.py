#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)
MAILBOX = 'Dazed'
OLD = '25'
NEW = '300'


class UpdateTest(object):
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
        event_new = event.get('new')
        event_old = event.get('old')

        if event_mailbox != MAILBOX or \
                event_new != NEW or \
                event_old != OLD:
            LOGGER.error("Unexpected values in AMI MessageWaiting event")
            self.fail_test()

        query = dict(id=event_mailbox)
        rt_row = self.rt_data.retrieve_row('mwi', query)
        if not rt_row:
            LOGGER.error("Mailbox %s in AMI event is not in realtime" %
                         event_mailbox)
            self.fail_test()
        LOGGER.debug("Row retrieved from realtime: %s" % rt_row)

        rt_mailbox = rt_row.get('id', '')
        rt_new = rt_row.get('msgs_new', '')
        rt_old = rt_row.get('msgs_old', '')

        if event_mailbox != rt_mailbox or \
                rt_new != event_new or \
                rt_old != event_old:
            LOGGER.error("AMI event and realtime data do not match")
            self.fail_test()

        self.pass_test()


def check_it(rt_data, test_object, ami):
    test = UpdateTest(rt_data, test_object, ami)

    ami.registerEvent('MessageWaiting', test.mwi_callback)
    message = {
        'Action': 'MWIUpdate',
        'Mailbox': MAILBOX,
        'OldMessages': OLD,
        'NewMessages': NEW,
    }
    ami.sendMessage(message)
