"""
Copyright (C) 2013, Digium, Inc.
Kevin Harwell <kharwell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

URL = 'deviceStates'
DEVICE = 'Stasis:Test'
INITIAL_STATE = 'NOT_INUSE'
CHANGED_STATE = 'INUSE'

def on_start(ari, event, obj):
    # add a device state
    ari.put(URL, DEVICE, deviceState=INITIAL_STATE)

    # subscribe to device
    ari.post("applications", "testsuite", "subscription",
             eventSource="deviceState:%s" % DEVICE)

    # subscribe to device
    ari.post("applications", "testsuite", "subscription",
             eventSource="deviceState:%s" % DEVICE)

    # change the device state
    ari.put(URL, DEVICE, deviceState=CHANGED_STATE)

    # unsubscribe from device
    ari.delete("applications", "testsuite", "subscription",
             eventSource="deviceState:%s" % DEVICE)

    # remove device
    ari.delete(URL, DEVICE)

    ari.delete('channels', event['channel']['id'])
    return True

def on_state_change(ari, event, obj):
    assert event['device_state']['name'] == DEVICE
    assert event['device_state']['state'] == CHANGED_STATE
    obj.stop_reactor()
    return True
