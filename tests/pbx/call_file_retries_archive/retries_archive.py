#!/usr/bin/env python
"""Call File Retries for Archive Option

Copyright (C) 2014, Digium, Inc.
Scott Emidy <jemidy@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
import logging

from twisted.internet import reactor

LOGGER = logging.getLogger(__name__)


class ArchiveCallFileRetry(object):
    """Checks whether the call file was archived or not"""
    def __init__(self, instance_config, test_object):
        """Constructor """
        super(ArchiveCallFileRetry, self).__init__()
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

    def archive_handler(self):
        """Archive File Handler """
        chk_dir = ("%s%s/outgoing_done/test0.call" %
                   (self.test_object.ast[int(self.call_file_config[0]['id'])]
                    .base, self.test_object.ast[int(self.call_file_config[0]
                    ['id'])].directories["astspooldir"]))

        if os.path.isfile(chk_dir):
            LOGGER.info('Call File Was Archived')
            LOGGER.info("Archive Location is %s" % chk_dir)
            self.test_object.set_passed(True)
            os.remove(chk_dir)
            self.test_object.stop_reactor()
        else:
            LOGGER.info('Call File Was Not Archived')
            self.test_failed()

    def user_event(self, ami, event):
        """Archive UserEvent Handler """
        if event['userevent'] != 'CallFileMaxRetries':
            return

        if event['result'] == 'archived':
            params = self.call_file_config[0].get('call-file-params')
            if params.get('Archive') != 'yes':
                LOGGER.error("Archive Was Not Set to Yes")
                self.test_failed()
            else:
                # needs a second to reach the outgoing_done folder
                reactor.callLater(1, self.archive_handler)
        else:
            LOGGER.error("Result Was Not Set to 'archived'")
            self.test_failed()

