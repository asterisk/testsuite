"""
Copyright (C) 2014, Digium, Inc.
Tyler Cambron <tcambron@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import logging

LOGGER = logging.getLogger(__name__)


def record(ami, event):
    """
    When the event specified in the test-config is triggered, the variable
    'channel' is set to the channelid of the channel where the event occurs.
    'channel' is then used to create the MixMonitor command message that is
    sent to asterisk to begin the recording of the playback.
    """
    channel = event.get('destchannel')
    if not channel:
        channel = event.get('channel')
    if not channel:
        return False
    message = {'Action': 'MixMonitor', 'Channel': '%s' % channel,
               'File': 'theRecording.wav', 'options': 'r'}
    ami.sendMessage(message)
    return True
