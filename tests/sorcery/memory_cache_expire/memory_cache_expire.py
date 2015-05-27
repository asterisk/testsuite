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

class MemoryCacheExpireTest(object):
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

    def expire_cache(self):
        def _expect_error(message):
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Error':
                self.fail_test()
            else:
                self.rt_data.add_row('endpoint', { 'id': ENDPOINT })
                self.retrieve_endpoint()

            return 0

        def _expired_cache(message):
            if type(message) is not dict:
                return 0

            if message.get('response') != 'Success':
                self.fail_test()
                return 0

            action = {
                'Action': 'PJSIPShowEndpoint',
                'Endpoint': ENDPOINT,
            }
            self.ami.sendMessage(action, responseCallback=_expect_error)

            return 0

        message = {
            'Action': 'SorceryMemoryCacheExpire',
            'Cache': CACHE,
        }
        self.ami.sendMessage(message, responseCallback=_expired_cache)

    def endpoint_detail_complete_callback(self, ami, event):
        self.endpoint_retrieved += int(event.get('listitems'))

        if self.endpoint_retrieved == 1:
             self.rt_data.delete_rows('endpoint', { 'id': ENDPOINT })
             self.retrieve_endpoint()
        elif self.endpoint_retrieved == 2:
             self.expire_cache()
        elif self.endpoint_retrieved == 3:
             self.pass_test()

def check_it(rt_data, test_object, ami):
    test = MemoryCacheExpireTest(rt_data, test_object, ami)

    ami.registerEvent('EndpointDetailComplete', test.endpoint_detail_complete_callback)

    test.retrieve_endpoint()
