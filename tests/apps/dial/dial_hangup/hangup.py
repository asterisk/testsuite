'''
Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

def send_hangup(ami, event):
    ''' Callback called when we detect dial has started.
    '''

    channel = event['channel']
    LOGGER.info('Hanging up channel %s' % channel)
    ami.hangup(channel)
    return True

