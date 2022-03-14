#!/usr/bin/env python
"""
Copyright (C) 2014, Digium, Inc.
Mark Michelson <mmichelson@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""


class UserEventGenerator(object):
    def __init__(self, instance_config, test_object):
        self.test_object = test_object
        self.userevents_received = 0
        test_object.register_ami_observer(self.ami_connect)

    def ami_connect(self, ami):
        ami.registerEvent('UserEvent', self.userevent)
        message = [
            b"FootBoneConnectedToThe: AnkleBone",
            b"AnkleBoneConnectedToThe: ShinBone",
            b"Action: UserEvent",
            b"ShinBoneConnectedToThe: KneeBone",
            b"UserEvent: AnatomyLesson",
            b"KneeBoneConnectedToThe: ThighBone",
        ]
        # We have to forego the typical methods of sending an AMI command
        # because the order the headers are sent in matters for this test.
        #
        # Using sendMessage or sendDeferred using the repeatedArgs param seems
        # like a potential alternative, but those methods automatically insert
        # an ActionId header as the first header. We want exactly the headers
        # we are sending in exactly the order we have them here in order to
        # verify proper operation.
        for _ in range(0, len(message)):
            message.append(message.pop(0))
            for line in message:
                ami.sendLine(line)
            ami.sendLine(b"")

    def userevent(self, ami, event):
        # This isn't strictly necessary, but without it, the test will take 30
        # seconds each run. With this, it's closer to ~6 seconds.
        self.userevents_received += 1
        if (self.userevents_received == 6):
            self.test_object.stop_reactor()
