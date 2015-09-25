#!/usr/bin/env python

import logging
LOGGER = logging.getLogger('test_runner')

class DevStateCheck(object):
    def __init__(self, config, test_object):
        self.test_object = test_object
        self.test_object.register_ami_observer(self.ami_connected)

    def ami_connected(self, ami):
        ami.registerEvent('DeviceStateChange', self.devstate_changed)
        ami.registerEvent('UserEvent', self.user_event)

    def devstate_changed(self, ami, event):
        '''When we see that Bob has been put on hold, we need to redirect Bob to
        the "echo" extension
        '''
        if (event.get('device') == 'PJSIP/bob' and
            event.get('state') == 'ONHOLD'):
            LOGGER.info("PJSIP/bob is on hold")
            message = {
                'action': 'redirect',
                'channel': 'PJSIP/bob-00000001',
                'context': 'default',
                'exten': 'echo',
                'priority': '1',
            }

            ami.sendMessage(message)

    def user_event(self, ami, event):
        '''When we have confirmation that Bob has been redirected, we need to
        ensure that Bob's device state is now INUSE. No matter if the test
        passes or fails, we also need to hang up Bob and Alice.
        '''
        def __getvar_cb(result):
            if result == 'INUSE':
                self.test_object.set_passed(True)
            else:
                LOGGER.error("PJSIP/bob device state is {0}".format(result))
                self.test_object.set_passed(False)

            ami.hangup('/.*/')

        LOGGER.info("Received UserEvent")
        ami.getVar(channel=None, variable="DEVICE_STATE(PJSIP/bob)"
                   ).addCallbacks(__getvar_cb)
