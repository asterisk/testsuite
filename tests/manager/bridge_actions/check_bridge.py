'''
Copyright (C) 2013, Digium, Inc.
Kinsey Moore <kmoore@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import logging

LOGGER = logging.getLogger(__name__)

class bridge_info_callback_container:
    def __init__(self, ami):
        self.ami = ami

    def callback(self, result):
        '''Ensure that only one bridge is listed and get detailed information about it
        '''
        channel_count = 0
        for list_result in result:
            if 'uniqueid' not in list_result:
                continue

            channel_count += 1

        if channel_count < 2:
            self.send_error("Not enough channels in the bridge")
        elif channel_count > 2:
            self.send_error("Too many channels in the bridge")
        else:
            self.send_success()

    def failed(self, reason):
        self.send_error("BridgeInfo action failed: %s" % reason)
        pass

    def send_error(self, message):
        LOGGER.error(message)
        self.ami.userEvent('BridgeInfoFailure', message=message})

    def send_success(self):
        self.ami.userEvent('BridgeInfoSuccess')

class bridge_list_callback_container:
    def __init__(self, ami):
        self.ami = ami

    def callback(self, result):
        '''Ensure that only one bridge is listed and get detailed information about it
        '''
        bridge_id = None
        for list_result in result:
            if 'bridgeuniqueid' not in list_result:
                continue

            if bridge_id is None:
                bridge_id = list_result['bridgeuniqueid']
            else:
                self.send_error("More than one bridge returned where there should be only one")
                return

        if bridge_id is None:
            self.send_error("No bridges returned where there should be one")
            return

        self.send_success()
        message = {
            'action' : 'BridgeInfo',
            'bridgeuniqueid' : bridge_id
        }
        info_callback = bridge_info_callback_container(self.ami)
        self.ami.collectDeferred(message, 'BridgeInfoComplete').addCallbacks(info_callback.callback, info_callback.failed)

    def failed(self, reason):
        self.send_error("BridgeList action failed: %s" % reason)
        pass

    def send_error(self, message):
        LOGGER.error(message)
        self.ami.userEvent('BridgeListFailure', message=message})

    def send_success(self):
        self.ami.userEvent('BridgeListSuccess')

def get_bridge_info(ami, event):
    ''' Callback called when the second participant entered the bridge.
    '''

    message = {
        'action' : 'BridgeList'
    }
    list_callback = bridge_list_callback_container(ami)
    ami.collectDeferred(message, 'BridgeListComplete').addCallbacks(list_callback.callback, list_callback.failed)
    return True
