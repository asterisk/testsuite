#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)

EXPECTED_MAILBOXES = 2
# Values from test-config.yaml
MAILBOXES = [
    {'mailbox': 'Dazed', 'new': '5', 'old': '4'},
    {'mailbox': 'Confused', 'new': '6', 'old': '8'}
]


class MultiTest(object):
    def __init__(self, rt_data, test_object, ami):
        self.rt_data = rt_data
        self.test_object = test_object
        self.ami = ami
        self.retrieved_mailboxes = 0

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def pass_test(self):
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def mwi_get_callback(self, ami, event):
        LOGGER.debug("Received MWI event %s" % event)
        self.retrieved_mailboxes += 1

        event_mailbox = event.get('mailbox')
        event_new = event.get('newmessages')
        event_old = event.get('oldmessages')

        check_mailbox = dict(mailbox=event_mailbox, new=event_new,
                             old=event_old)

        if check_mailbox not in MAILBOXES:
            LOGGER.error("Unexpected values in MWIGet event")
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

    def mwi_get_complete_callback(self, ami, event):
        if self.retrieved_mailboxes != EXPECTED_MAILBOXES:
            LOGGER.error("Did not retrieve the expected number of mailboxes,"
                         " %d != %d" % (self.retrieved_mailboxes,
                                        EXPECTED_MAILBOXES))
            self.fail_test()
        else:
            self.pass_test()


def check_it(rt_data, test_object, ami):
    test = MultiTest(rt_data, test_object, ami)

    ami.registerEvent('MWIGet', test.mwi_get_callback)
    ami.registerEvent('MWIGetComplete', test.mwi_get_complete_callback)
    message = {
        'Action': 'MWIGet',
        'Mailbox': '/^/',
    }
    ami.sendMessage(message)
