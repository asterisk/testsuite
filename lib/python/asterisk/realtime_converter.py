#!/usr/bin/env python
"""
Copyright (C) 2016, Digium, Inc.

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
from sqlalchemy import create_engine, MetaData, Table

from . import astconfigparser
import logging

LOGGER = logging.getLogger(__name__)

"""Registry of files convertable to realtime

This is a list of objects that conform to the following specifications:
    * An __init__ method that takes a filename and some object. The filename is
      the name of the file that can be converted to realtime. The object is a
      conversion-specific field that tells the converter how to convert objects.

    * A write_configs method that takes a directory as a parameter. This method
      is responsible for writing additional configuration information for
      Asterisk to use when running a test in realtime mode.

    * A write_db method that takes a MetaData, Engine, and Connection. This
      method is responsible for writing data to the database for the file that
      is being converted

    * A cleanup_configs method that takes no parameters. This is responsible
      for removing configuration information that was originally written by
      this converter.

    * A cleanup_db method that takes a MetaData, Engine, and Connection. This
      method is responsible for deleting data from the database originally
      written by this converter
"""
REALTIME_FILE_REGISTRY = []


class ConfigFile(object):
    """A config file to be written by a realtime converter

    When the realtime converter is enacted, it is unknown if the relevant
    configuration file it wants to write exists already for the given test. This
    class offers a simple way to ensure that the file is restored to its
    pre-test-run state.
    """

    def __init__(self, config_dir, filename):
        self.file = os.path.join(config_dir, filename)
        self.orig_file_content = None
        if os.path.exists(self.file):
            with open(self.file, 'r') as config:
                self.orig_file_content = config.read()

    def restore(self):
        if not self.orig_file_content:
            os.remove(self.file)
            return

        with open(self.file, 'w') as config:
            config.write(self.orig_file_content)


class SorceryRealtimeFile(object):
    """A Realtime Converter that works for sorcery-managed configuration

    This converter can be used for any type of configuration file that is
    managed by sorcery. This is because object types used by configuration files
    and by realtime are identical when sorcery manages the configuration.
    """
    def __init__(self, filename, sections):
        """Initialize the sorcery converter

        Keyword Arguments:
        filename: The name of the file to convert to database
        sections: A dictionary of sorcery.conf sections, containing dictionaries
                  that map object names to table names.
        """
        self.filename = filename
        self.sections = sections
        # All affected database tables in list form. Used for convenience
        self.tables = [table for section in sections.values() for table in
                       section.values()]
        self.sorcery = None
        self.extconfig = None

    def write_configs(self, config_dir, asterisk):
        """Write configuration for sorcery.

        This writes the sorcery.conf file and adds to the extconfig.conf file in
        order to convert a file to database configuration

        Keyword Arguments:
        config_dir: The directory where Asterisk configuration can be found
        """
        self.sorcery = ConfigFile(config_dir, 'sorcery.conf')
        self.extconfig = ConfigFile(config_dir, 'extconfig.conf')
        self.write_sorcery_conf()
        self.write_extconfig_conf()
        asterisk.install_config(os.path.join(config_dir, 'sorcery.conf'))
        asterisk.install_config(os.path.join(config_dir, 'extconfig.conf'))

    def write_sorcery_conf(self):
        """Write sorcery.conf file.

        Keyword Arguments:
        config_dir: The directory where Asterisk configuration can be found
        """
        with open(self.sorcery.file, 'a') as sorcery:
            for section, items in self.sections.items():
                sorcery.write('[{0}]\n'.format(section))
                for obj, table in items.items():
                    sorcery.write('{0} = realtime,{1}\n'.format(obj, table))

    def write_extconfig_conf(self):
        """Write extconfig.conf file.

        Keyword Arguments:
        config_dir: The directory where Asterisk configuration can be found
        """
        with open(self.extconfig.file, 'a') as extconfig:
            for table in self.tables:
                # We can assume "odbc" and "asterisk" here because we're
                # currently only supporting the ODBC realtime engine, and
                # "asterisk" refers to the name of the config section in
                # res_odbc.conf.
                extconfig.write('{0} = odbc,asterisk\n'.format(table))

    def write_db(self, config_dir, meta, engine, conn):
        """Convert file contents into database entries

        Keyword Arguments:
        config_dir: Location of file to convert
        meta: sqlalchemy Metadata
        engine: sqlalchemy Engine used for database management
        conn: sqlaclemy Connection to the database
        """
        conf = astconfigparser.MultiOrderedConfigParser()
        conf.read(os.path.join(config_dir, self.filename))
        for title, sections in conf.sections().items():
            LOGGER.info("Inspecting objects with title {0}".format(title))
            for section in sections:
                obj_type = section.get('type')[0]
                sorcery_section = self.find_section_for_object(obj_type)
                if not sorcery_section:
                    LOGGER.info("No corresponding section found for object "
                                "type {0}".format(obj_type))
                    continue
                table = Table(self.sections[sorcery_section][obj_type], meta,
                              autoload=True, autoload_with=engine)
                vals = {'id': title}
                for key in section.keys():
                    if key != 'type':
                        vals[key] = ";".join(value.replace(";", "^3B") for value in section.get(key))

                conn.execute(table.insert().values(**vals))

    def find_section_for_object(self, obj_type):
        """Get the sorcery.conf section a particular object type belongs to

        Keyword Arguments:
        obj_type: The object type to find the section for
        """
        for section, contents in self.sections.items():
            if obj_type in contents:
                return section

        return None

    def cleanup_configs(self):
        """Remove sorcery.conf file after test completes

        Keyword Arguments:
        config_dir: Location of sorcery.conf file
        """
        self.extconfig.restore()
        self.sorcery.restore()

    def cleanup_db(self, meta, engine, conn):
        """Remove database entries after test completes

        Keyword Arguments:
        meta: sqlalchemy MetaData
        engine: sqlalchemy Engine
        conn: sqlalchemy Connection to database
        """
        for table_name in self.tables:
            table = Table(table_name, meta, autoload=True,
                          autoload_with=engine)
            conn.execute(table.delete())


class RealtimeConverter(object):
    """Pluggable module used to convert configuration files to database data.

    Since this uses the pluggable module framework, it can be applied to
    individual tests if desired.

    However, this module will see its highest use as configured in the global
    test-config.yaml for the testsuite. In that case, all tests that use the
    pluggable module framework will automaticaly have this module plugged in,
    resulting in all tests running in realtime mode if possible. It is
    recommended that if only a subset of tests are desired to be run, then
    adding tags to the desired tests would be a good idea.

    WARNING: Do not attempt to use this plugin both as a local and global
    pluggable module. Doing so will likely have weird effects both on the
    database and configuration files in the test.
    """
    def __init__(self, config, test_object):
        """Initialize the converter.

        Keyword Arguments:
        config: Database configuration information
        test_object: The test object for the particular test
        """
        engine = config.get('engine', 'postgresql')
        username = config.get('username', 'asterisk')
        password = config.get('password', 'asterisk')
        host = config.get('host', 'localhost')
        port = config.get('port', '5432')
        database = config.get('db', 'asterisk')
        dsn = config.get('dsn', 'asterisk')

        # XXX This is currently a limitation we apply to automatic realtime
        # conversion. We only will convert the first Asterisk instance to use
        # realtime. This is because we currently only allow for the
        # configuration of one database in the DBMS.
        self.config_dir = os.path.join(test_object.test_name, "configs", "ast1")

        test_object.register_stop_observer(self.cleanup)

        self.meta = MetaData()
        self.engine = create_engine('{0}://{1}:{2}@{3}:{4}/{5}'.format(engine,
            username, password, host, port, database), echo=False)
        self.conn = self.engine.connect()

        self.modules_conf_exists = False
        self.modules_conf = None

        self.extconfig = ConfigFile(self.config_dir, 'extconfig.conf')
        self.res_odbc = ConfigFile(self.config_dir, 'res_odbc.conf')
        self.modules = ConfigFile(self.config_dir, 'modules.conf.inc')
        self.write_extconfig_conf()
        self.write_res_odbc_conf(dsn, username, password)
        self.write_modules_conf()
        test_object.ast[0].install_config(os.path.join(self.config_dir,
                                                       'extconfig.conf'))
        test_object.ast[0].install_config(os.path.join(self.config_dir,
                                                       'res_odbc.conf'))
        test_object.ast[0].install_config(os.path.join(self.config_dir,
                                                       'modules.conf.inc'))
        for realtime_file in REALTIME_FILE_REGISTRY:
            realtime_file.write_configs(self.config_dir, test_object.ast[0])

        try:
            self.write_db()
        except:
            self.cleanup(None)
            raise

    def write_extconfig_conf(self):
        """Write the initial extconfig.conf information

        This only consists of writing "[settings]" to the top of the file. The
        rest of the contents of this file will be written by individual file
        converters.
        """
        if self.extconfig.orig_file_content:
            # Bail early. There is presumably already a [settings] section here,
            # so there is no reason to try to do anything else.
            return

        with open(self.extconfig.file, 'w') as extconfig:
            extconfig.write('[settings]\n')

    def write_res_odbc_conf(self, dsn, username, password):
        """Write res_odbc.conf file

        This uses database configuration to set appropriate information in
        res_odbc.conf. Individual converters should have no reason to edit this
        file any further
        """
        with open(self.res_odbc.file, 'w') as res_odbc:
            res_odbc.write('''[asterisk]
enabled = yes
pre-connect = yes
dsn = {0}
username = {1}
password = {2}
'''.format(dsn, username, password))

    def write_modules_conf(self):
        """Write modules.conf.inc file"""
        with open(self.modules.file, 'a+') as modules:
            modules.write('preload => res_odbc.so\npreload=>res_config_odbc.so')

    def write_db(self):
        """Tell converters to write database information"""
        for realtime_file in REALTIME_FILE_REGISTRY:
            realtime_file.write_db(self.config_dir, self.meta, self.engine,
                                   self.conn)

    def cleanup(self, result):
        """Cleanup information after test has completed.

        This will call into registered converters to clean themselves up, and
        then will restore all written configuration to their pre-test state

        Keyword Arguments:
        result: Running result of stop observer callbacks.
        """
        for realtime_file in REALTIME_FILE_REGISTRY:
            realtime_file.cleanup_configs()
            realtime_file.cleanup_db(self.meta, self.engine, self.conn)
        self.res_odbc.restore()
        self.extconfig.restore()
        self.modules.restore()
        self.conn.close()
        return result


REALTIME_FILE_REGISTRY.append(SorceryRealtimeFile('pjsip.conf',
    # We don't include the following object types in this dictionary:
    # * system
    # * transport
    # The first two don't work especially well for dynamic realtime since they
    # are not reloadable.
    #
    # The table names here are the ones that the alembic scripts use.
    {
        'res_pjsip': {
            'endpoint': 'ps_endpoints',
            'aor': 'ps_aors',
            'auth': 'ps_auths',
            'global': 'ps_globals',
            'domain_alias': 'ps_domain_aliases',
            'contact': 'ps_contacts',
        },
        'res_pjsip_endpoint_identifier_ip': {
            'identify': 'ps_endpoint_id_ips',
        },
        'res_pjsip_outbound_registration': {
            'registration': 'ps_registrations',
        },
        'res_pjsip_pubsub': {
            'subscription_persistence': 'ps_subscription_persistence'
        },
    }
))
