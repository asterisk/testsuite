'''
Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

def optimize_channel(ami, event):
    ''' Callback called when we decide to try and optimize the Local channel '''

    LOGGER.info('Requesting Local channel optimization')
    msg = {'Action': 'LocalOptimizeAway',
           'Channel': 'Local/dial_bar@default-00000000;1',}
    ami.sendMessage(msg)
    return True
