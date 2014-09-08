#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


class MWISender(object):
    '''Test module that updates MWI on the sending Asterisk server.

    This reads test module configuration from test-config.yaml to determine
    what MWIUpdate AMI commands to send in order to complete the test.
    '''
    def __init__(self, module_config, test_object):
        self.config = module_config
        test_object.register_ami_observer(self.ami_connect)

    def ami_connect(self, ami):
        '''Send configured AMI MWIUpdate commands'''
        if ami.id == 1:
            # ID 1 is the receiving Asterisk server.
            return

        for msg in self.config['messages']:
            ami_msg = {
                'Action': 'MWIUpdate',
                'Mailbox': self.config['mailbox'],
                'NewMessages': msg['new'],
                'OldMessages': msg['old'],
            }
            ami.sendMessage(ami_msg)
