#!/usr/bin/env python

'''
Copyright (C) 2015, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)
ENDPOINT = 'test'
CACHE = 'res_pjsip/endpoint'

class MemoryCacheStaleTest(object):
    def __init__(self, rt_data, test_object, ami):
        self.rt_data = rt_data
        self.test_object = test_object
        self.ami = ami
        self.endpoint_retrieved = 0

    def fail_test(self):
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def pass_test(self):
        self.test_object.set_passed(True)
        self.test_object.stop_reactor()

    def retrieve_endpoint(self):
        message = {
            'Action': 'PJSIPShowEndpoint',
            'Endpoint': ENDPOINT,
        }
        self.ami.sendMessage(message)

    def retrieve_endpoint_and_fail(self, ami, event):
        def _expect_error(message):
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Error':
                self.fail_test()
                return 0

            self.pass_test()

            return 0

        message = {
            'Action': 'PJSIPShowEndpoint',
            'Endpoint': ENDPOINT,
        }
        self.ami.sendMessage(message, responseCallback=_expect_error)

    def stale_cache(self):
        def _cache_marked_as_stale(message):
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Success':
                self.fail_test()
                return 0

            self.ami.registerEvent('TestEvent', self.retrieve_endpoint_and_fail)

            self.retrieve_endpoint()

            return 0

        message = {
            'Action': 'SorceryMemoryCacheStale',
            'Cache': CACHE,
        }
        self.ami.sendMessage(message, responseCallback=_cache_marked_as_stale)

    def endpoint_detail_complete_callback(self, ami, event):
        self.endpoint_retrieved += int(event.get('listitems'))

        if self.endpoint_retrieved == 1:
             self.rt_data.delete_rows('endpoint', { 'id': ENDPOINT })
             self.stale_cache()
        elif self.endpoint_retrieved == 3:
             self.fail_test()

def check_it(rt_data, test_object, ami):
    test = MemoryCacheStaleTest(rt_data, test_object, ami)

    ami.registerEvent('EndpointDetailComplete', test.endpoint_detail_complete_callback)

    test.retrieve_endpoint()
