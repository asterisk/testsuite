#!/usr/bin/env python
"""
Copyright (C) 2016, Digium, Inc.
Scott Griepentrog <sgriepentrog@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""
import os
import logging


LOGGER = logging.getLogger(__name__)


class RealtimeOdbcModule(object):
    """Test module for realtime database tests using unixODBC.

    This module configures unixODBC and Asterisk for realtime database
    use.  The __init__() is called at a point where the configuration
    files for the Asterisk test instance have been written, but prior
    to starting Asterisk.

    The module config should look something like this (the Database
    entry is an sqlite3 file preloaded with the database data, and
    is located in configs/ast1 which will be copied to etc/asterisk):

    odbc-config:
        asterisk:
            # consult /etc/odbcinst.ini, borrow entry with this driver
            use-driver: 'libsqlite3odbc'
            odbcinst:
                # odbcinst values from copied from /etc can be overwritten here
                Threading: '0'
                Pooling: 'yes'
                CPTimeout: '120'
                UsageCount: '2'
            odbc:
                # Driver=(name of odbcinst entry) added automatically
                Database: 'etc/asterisk/asterisk.sqlite3'
                # Database: 'asterisk'
                Description: 'Test Database'
            res_odbc:
                # 'dsn => asterisk' added automatically from key one level up
                enabled: 'yes'
                pre-connect: 'yes'
                max_connections: '20'
    """
    def __init__(self, module_config, test_object):
        self.test_object = test_object
        self.odbcinst = {}
        self.odbc = {}
        self.res_odbc = {}

        # generate configuration for each dsn
        for dsn, config in module_config.items():
            self._configure(dsn, config)

        # set the odbc and conf files
        etc = test_object.ast[0].base + '/etc'
        odbcinst_path = etc + '/odbcinst.ini'
        odbc_path = etc + '/odbc.ini'
        res_odbc_path = etc + '/asterisk/res_odbc.conf'

        # write the odbc ini and conf files
        self._write_ini_file(odbcinst_path, self.odbcinst)
        self._write_ini_file(odbc_path, self.odbc)
        self._write_ini_file(res_odbc_path, self.res_odbc)

        # inform ODBC where to find them
        os.environ['ODBCSYSINI'] = etc

    def _configure(self, dsn, config):
        match_driver = config.get('use-driver', 'libsqlite3odbc')

        inst = self._read_ini_file('/etc/odbcinst.ini')
        found_driver = None
        for section in inst:
            driver = inst[section].get('Driver')
            if driver and match_driver in driver:
                found_driver = section
                break

        if not found_driver:
            LOGGER.error('Unable to find odbcinst entry matching driver ' +
                         repr(match_driver))
            return

        # create a unique driver name by adding the dsn
        driver_name = found_driver + '_' + dsn

        self.odbcinst[driver_name] = inst[found_driver]
        self.odbcinst[driver_name].update(config.get('odbcinst', {}))

        self.odbc[dsn] = {'Driver': driver_name}
        self.odbc[dsn].update(config.get('odbc', {}))

        self.res_odbc[dsn] = {'dsn': dsn}
        self.res_odbc[dsn].update(config.get('res_odbc', {}))

        # update the Database path if relative
        Database = self.odbc[dsn].get('Database', None)
        if Database and Database[0] != '/' and '/' in Database:
            self.odbc[dsn]['Database'] = '/'.join([
                self.test_object.ast[0].base,
                Database])

    def _write_ini_file(self, filepath, contents):
        with open(filepath, 'w') as filehandle:
            for section in contents:
                filehandle.write('[' + section + ']\n')
                for name, value in contents[section].items():
                    filehandle.write(name + '=' + value + '\n')

    def _read_ini_file(self, filepath):
        contents = {}
        with open(filepath) as filehandle:
            for line in filehandle.readlines():
                if line.startswith('['):
                    section = line.rstrip()[1:-1]
                    contents[section] = {}
                elif '=' in line:
                    name, value = line.rstrip().split('=')
                    contents[section][name.strip()] = value.strip()
        return contents
