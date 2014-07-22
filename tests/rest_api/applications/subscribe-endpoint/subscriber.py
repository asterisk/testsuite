#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)

class ResourceSubscription(object):
    """Pluggable module that subscribes to a resource"""

    def __init__(self, module_config, test_object):
        """Constructor

        Keyword Arguments:
        module_config This object's configuration
        test_object   The one and only test object
        """
        super(ResourceSubscription, self).__init__()

        self.module_config = module_config
        self.test_object = test_object

        self.subscribe_only = module_config.get('subscribe-only', False)

        test_object.register_ami_observer(self._handle_ami_connection)

    def _handle_ami_connection(self, ami):
        """Called when the AMI connection is made

        Keyword Arguments:
        ami  Our AMI protocol wrapper
        """

        ami_id = self.module_config.get('id', 0)
        if ami.id != ami_id:
            return

        ari = self.test_object.ari
        for sub in self.module_config.get('subscriptions'):
            app = sub.get('app', 'testsuite')
            expected_response = sub.get('expected-response')
            if expected_response:
                ari.set_allow_errors(True)

            resp = ari.post("applications", app, "subscription",
                            eventSource="%s" % sub['event-source'])

            if expected_response:
                if resp.status_code != expected_response:
                    LOGGER.error('Failed to get expected response %d: Got %d' %
                        (expected_response, resp.status_code))
                    self.test_object.set_passed(False)
                else:
                    LOGGER.info('Got expected response %d for %s' %
                        (expected_response, sub['event-source']))
                    self.test_object.set_passed(True)
            ari.set_allow_errors(False)

        if self.subscribe_only:
            self.test_object.stop_reactor()
