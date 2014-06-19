#!/usr/bin/env python

import logging

LOGGER = logging.getLogger(__name__)

EXPECTED_ENDPOINTS = 1
# Values from test-config.yaml
ENDPOINT = 'alice'
CONTEXT = 'fabulous'


class StaticTest(object):
    def __init__(self, rt_data, test_object, ami):
        self.rt_data = rt_data
        self.test_object = test_object
        self.ami = ami
        self.num_endpoints = 0

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def pass_test(self):
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def endpoint_detail_callback(self, ami, event):
        LOGGER.debug("Received EndpointDetail event %s" % event)
        self.num_endpoints += 1
        if event['objectname'] != ENDPOINT or \
                event['context'] != CONTEXT:
            LOGGER.error("Unexpected data in EndpointDetail event")
            self.fail_test()

    def endpoint_detail_complete_callback(self, ami, event):
        LOGGER.debug("Received EndpointDetailComplete event %s" % event)
        if self.num_endpoints != EXPECTED_ENDPOINTS:
            self.fail_test()
        else:
            self.pass_test()


def check_it(rt_data, test_object, ami):
    test = StaticTest(rt_data, test_object, ami)

    ami.registerEvent('EndpointDetail', test.endpoint_detail_callback)
    ami.registerEvent('EndpointDetailComplete',
                      test.endpoint_detail_complete_callback)
    message = {
        'Action': 'PJSIPShowEndpoint',
        'Endpoint': ENDPOINT,
    }
    ami.sendMessage(message)
