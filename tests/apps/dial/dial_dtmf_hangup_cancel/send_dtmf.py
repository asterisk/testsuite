'''
Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

def send_dtmf(ami, event):
    ''' Callback called when we detect dial has started.
    '''

    channel = event['channel'][:len(event['channel']) - 2]
    channel += ';1'
    LOGGER.info('Sending DTMF to hangup channel %s' % channel)
    ami.redirect(channel, 'default', 'dtmf', '1')
    return True
