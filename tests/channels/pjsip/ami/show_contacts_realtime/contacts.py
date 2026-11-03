"""Populate realtime AORs for the PJSIPShowContacts test.

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
import sqlite3
from contextlib import closing


class RealtimeContacts:
    """Provide permanent contacts without any endpoint references."""

    # Seed an isolated database before Asterisk loads its realtime AORs.
    def __init__(self, module_config, test_object):
        path = os.path.join(test_object.ast[0].astetcdir, 'contacts.sqlite3')
        with closing(sqlite3.connect(path)) as database:
            database.execute('CREATE TABLE ps_aors (id TEXT PRIMARY KEY, '
                             'contact TEXT)')
            database.executemany('INSERT INTO ps_aors VALUES (?, ?)', [
                ('static1', 'sip:static1@127.0.0.1:5062'),
                ('static2', 'sip:static2@127.0.0.1:5063'),
                ('empty', ''),
            ])
            database.commit()
