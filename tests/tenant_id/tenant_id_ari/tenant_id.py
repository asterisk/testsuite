'''
Copyright (C) 2024, Sangoma, Inc.
Ben Ford <bford@sangoma.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

def on_stasis_start(ari, event, obj):
    channel = event.get('channel')
    tenantid = channel.get('tenantid')
    assert(tenantid == 'Test ID')
    ari.delete('channels', event['channel']['id'])
    return True
