#!/usr/bin/env python
'''
Copyright (C) 2014, Digium, Inc.
Joshua Colp <jcolp@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''


class DialogInfoXML(object):
    def __init__(self, module_config, test_object):
        self.ami = None
        # Device state defaults to NOT_INUSE.
        self.device_state = "NOTINUSE"
        test_object.register_ami_observer(self.ami_connect)

    def test_event(self, ami, event):
        if event.get("state") != "SUBSCRIPTION_STATE_SET":
            return

        if self.device_state == "NOTINUSE":
            self.device_state = "RINGING"
        elif self.device_state == "RINGING":
            self.device_state = "INUSE"
        elif self.device_state == "INUSE":
            self.device_state = "ONHOLD"

        message = {
            'Action': 'SetVar',
            'Variable': 'DEVICE_STATE(Custom:presence)',
            'Value': self.device_state
        }
        self.ami.sendMessage(message)

    def ami_connect(self, ami):
        self.ami = ami
        self.ami.registerEvent("TestEvent", self.test_event)
