#!/usr/bin/env python
"""Pluggable module for the sqlite3 test

Copyright (C) 2013, Digium, Inc.
Matt Jordan <mjordan@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import logging
import sqlite3
import re

sys.path.append("lib/python")
from asterisk.config import ConfigFile

LOGGER = logging.getLogger(__name__)

class CDRSQLite3Verifier(object):
    """A class that verifies CDRs in SQLite3 records"""


    def __init__(self, module_config, test_object):
        """Constructor"""

        self.module_config = module_config
        self.test_object = test_object

        # Hook ourselves onto the test object
        test_object.register_stop_observer(self.check_cdr_records)


    def verify_record(self, actual, expected):
        """Verify two records are the same

        Note that we allow fields in actual to exist that aren't
        in expected. Every field in expected should exist in the
        actual record.

        Keyword Arguments:
        actual The actual record retrieved
        expected The expected record

        Returns:
        True if the two records are a match
        False otherwise
        """

        for expected_key, expected_value in expected.items():
            if expected_key not in actual:
                LOGGER.debug("Field %s is not in actual record" % expected_key)
                return False

            actual_value = actual[expected_key]
            if not re.match(expected_value.lower(),
                            actual_value.strip().lower()):
                LOGGER.debug("Field %s: actual %s != expected %s" %
                    (expected_key, actual_value, expected_value))
                return False
        return True

    def get_sqlite_config(self, ast_instance):
        """Retrieve necessary SQLite3 config parameters from the config file

        Keyword Arguments:
        ast_instance The instance of Asterisk that used the config file

        Returns:
        Tuple of (table, columns)
        """
        sqlite_config_file = ("%s/%s/cdr_sqlite3_custom.conf" %
                              (ast_instance.base,
                               ast_instance.directories['astetcdir']))

        sqlite_config = ConfigFile(sqlite_config_file)
        for option in sqlite_config.categories[0].options:
            if option[0] == 'table':
                table = option[1]
            elif option[0] == 'columns':
                columns = [col.strip() for col in option[1].split(',')]
        return (table, columns)

    def check_cdr_records(self, callback_param):
        """A deferred callback method that is called by the TestCase
        derived object when all Asterisk instances have stopped

        Parameters:
        callback_param
        """

        overall_success = []

        for instance in self.module_config:
            instance = instance or {}
            ast_index = instance.get('asterisk-instance') or 0
            database = instance.get('database') or 'master.db'
            lines = instance.get('lines')

            if not lines:
                LOGGER.warning('No expected CDR entries in config?')
                continue

            ast_instance = self.test_object.ast[ast_index]

            LOGGER.debug("Checking CDR records from %s" % ast_instance.host)

            table, columns = self.get_sqlite_config(ast_instance)

            sqlite_database = "%s/%s/%s" % (ast_instance.base,
                 ast_instance.directories['astlogdir'],
                 database)

            conn = sqlite3.connect(sqlite_database)
            cursor = conn.cursor()
            cursor.execute("SELECT %s FROM %s" % (','.join(columns), table))
            entries = cursor.fetchall()

            # Convert each SQL result to a dictionary of columns, values
            cdr_entries = [dict(zip(columns, list(entry))) for entry in entries]
            if len(cdr_entries) != len(lines):
                LOGGER.error("Expected entries %d != actual number %d" %
                    (len(lines), len(cdr_entries)))
                overall_success.append(False)
                continue

            # Test each against the expected
            for cdr_entry in cdr_entries:
                new_lines = [line for line in lines if
                             not self.verify_record(cdr_entry, line)]
                success = (len(new_lines) != len(lines))
                if not success:
                    LOGGER.error("CDR record %s failed to match any expected" %
                        str(cdr_entry))
                overall_success.append(success)

                lines = new_lines

            conn.close()

        self.test_object.set_passed(all(overall_success))
        return callback_param



