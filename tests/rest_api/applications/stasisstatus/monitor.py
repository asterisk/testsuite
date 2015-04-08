#!/usr/bin/env python
"""
Copyright (C) 2015, Digium, Inc.
Ashley Sanders <asanders@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging

sys.path.append("lib/python")
sys.path.append("tests/rest_api/applications")

from stasisstatus.observable_object import ObservableObject

LOGGER = logging.getLogger(__name__)


class ChannelVariableMonitor(ObservableObject):
    """Monitors the system for state changes for a given channel variable."""

    def __init__(self, ami, variable, name):
        """Constructor.

        Keyword Arguments:
        ami                    -- The AMI instance to monitor.
        variable               -- The name of the channel variable to monitor
                                  (optional) (default None).
        name                   -- The name of this ChannelVariableMonitor
                                  instance.
        """

        super(ChannelVariableMonitor, self).__init__(name,
                                                    ['on_value_changed'])
        self.__ami = ami
        self.__captured_value = None
        self.__channel_variable = variable
        self.__monitored_channel = None

        self.__ami.registerEvent('VarSet', self.__on_ami_varset)
        self.__ami.registerEvent('UserEvent', self.__on_ami_user_event)

    def __log_event(self, handler, event_data):
        """Logs event messages.

        Keyword Arguments:
        handler                -- The name of the event handler.
        event_data             -- The event payload or message.
        """

        LOGGER.debug('{0} In {1}; event data={2}'.format(self,
                                                         handler,
                                                         event_data))

    def __on_ami_user_event(self, ami, message):
        """Handles the AMI 'UserEvent' event.

        Keyword Arguments:
        ami                   -- The AMI instance.
        message               -- The event payload.
        """

        if message['uniqueid'] != self.__monitored_channel:
            return

        if message['userevent'] != 'StasisStatus':
            return

        self.captured_value = message['value']

    def __on_ami_varset(self, ami, message):
        """Handles the AMI 'VarSet' event.

        Keyword Arguments:
        ami                   -- The AMI instance.
        message               -- The event payload.
        """

        self.__log_event('__on_ami_varset', message)

        msg = '{0} '.format(self)

        if self.suspended:
            LOGGER.debug(msg + 'Monitoring is suspended.')
            return

        if message['uniqueid'] != self.__monitored_channel:
            return
        if message['variable'] != self.__channel_variable:
            return

        self.captured_value = message['value']

    def start(self, channel):
        """Tells the monitor to start monitoring for the given channel.

        Keyword Arguments:
        channel               -- The id of the channel to use for monitoring.
        """

        LOGGER.debug('{0} Monitoring starting for channel[{1}]'.format(self,
                                                                       channel))
        self.__monitored_channel = channel
        self.activate()

    @property
    def captured_value(self):
        """The current value captured for the monitored channel variable."""

        return self.__captured_value

    @captured_value.setter
    def captured_value(self, value):
        """Sets the captured value."""

        self.__captured_value = value
        LOGGER.debug('{0} {1}={2}.'.format(self,
                                           self.__channel_variable,
                                           self.__captured_value))
        self.notify_observers('on_value_changed', None, False)

