#!/usr/bin/env python
"""Call File Retries for AlwaysDelete Option

Copyright (C) 2014, Digium, Inc.
Scott Emidy <jemidy@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
import logging

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class AlwaysDeleteCallFileRetry(object):
    """Checks whether the call file was deleted or not after execution """
    def __init__(self, instance_config, test_object):
        """Constructor """
        super(AlwaysDeleteCallFileRetry, self).__init__()
        self.test_object = test_object
        self.call_file_config = instance_config

        if self.call_file_config:
            self.test_object.register_ami_observer(self.ami_connect)
        else:
            LOGGER.error("No configuration was specified for call files")
            self.test_failed()

    def ami_connect(self, ami):
        """Handler for AMI Connection """
        ami.registerEvent('UserEvent', self.user_event)

    def test_failed(self):
        """Checks to see whether or not the call files were
           correctly specified """
        self.test_object.set_passed(False)
        self.test_object.stop_reactor()

    def alwaysdelete_handler(self):
        """AlwaysDelete File Handler """
        dst_file = ("%s%s/outgoing/test0.call" %
                    (self.test_object.ast[int(self.call_file_config[0]['id'])]
                     .base,self.test_object.ast[int(self.call_file_config[0]
                     ['id'])].directories["astspooldir"]))

        if os.path.isfile(dst_file):
            LOGGER.info('Call File Was Not Deleted')
            LOGGER.info('AlwaysDelete Location is %s' % dst_file)
            self.test_object.set_passed(True)
            os.remove(dst_file)
            self.test_object.stop_reactor()
        else:
            LOGGER.error('Call File Was Executed and Deleted')
            self.test_failed()

    def user_event(self, ami, event):
        """AlwaysDelete UserEvent Handler """
        if event['userevent'] != 'CallFileMaxRetries':
            return

        if event['result'] == 'deleted':
            params = self.call_file_config[0].get('call-file-params')
            if params.get('AlwaysDelete') != 'no':
                LOGGER.error("AlwaysDelete Was Not Set to 'no'")
                self.test_failed()
            else:
                self.alwaysdelete_handler()
        else:
            LOGGER.error("Result Was Not Set to 'deleted'")
            self.test_failed()
