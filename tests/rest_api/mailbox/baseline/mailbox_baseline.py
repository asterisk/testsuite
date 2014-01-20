'''
Copyright (C) 2014, Digium, Inc.
Jonathan Rose <jrose@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import requests
import logging
import operator

LOGGER = logging.getLogger(__name__)

def on_start(ari, event, obj):
    mailboxes = ari.get('mailboxes').json()
    assert len(mailboxes) == 0

    LOGGER.info("Confirmed mailboxes started empty.")

    ari.put('mailboxes', 'alice_mailbox', oldMessages='3', newMessages='4')
    ari.put('mailboxes', 'bob_mailbox', oldMessages='5', newMessages='6')

    LOGGER.info("Successfully added mailboxes");

    # Get a specific mailbox
    mailbox = ari.get('mailboxes', 'alice_mailbox').json()
    assert mailbox
    assert mailbox['name'] == 'alice_mailbox'
    assert mailbox['old_messages'] == 3
    assert mailbox['new_messages'] == 4

    LOGGER.info("Successfully retrieved single mailbox and confirmed contents"
                " matched expectations")

    # Get the list of mailboxes
    mailboxes = ari.get('mailboxes').json()
    assert mailboxes

    mailboxes = sorted(mailboxes, key=operator.itemgetter('name'))
    expected = [
        {"name": "bob_mailbox", "old_messages": 5, "new_messages": 6},
        {"name": "alice_mailbox", "old_messages": 3, "new_messages": 4}
    ]
    expected = sorted(expected, key=operator.itemgetter('name'))

    assert(mailboxes == expected)

    LOGGER.info("Successfully listed mailboxes and checked contents for expectations")

    # Change a mailbox
    ari.put('mailboxes', 'alice_mailbox', oldMessages='11', newMessages='3')

    # Delete a mailbox
    ari.delete('mailboxes', 'bob_mailbox')

    mailboxes = ari.get('mailboxes').json()
    assert mailboxes
    assert len(mailboxes) == 1

    expected = [
        {"name": "alice_mailbox", "old_messages": 11, "new_messages": 3}
    ]

    assert mailboxes == expected

    LOGGER.info("Changed alice_mailbox. Confirmed new values.")
    LOGGER.info("Deleted bob_mailbox. Confirmed removal from list.")

    # While this test doesn't actually use the channel for any of the ARI
    # operations that it does, its presence is necessary for triggering
    # the test and removing it is necessary for completing the test.
    ari.delete('channels', event['channel']['id'])
    return True
