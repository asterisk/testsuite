#!/usr/bin/env python
""" Asterisk Instances in Python.

This module provides an interface for creating instances of Asterisk
from within python code.

Copyright (C) 2010-2012, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import time
import shutil
import logging

import TestSuiteUtils

from config import ConfigFile
from version import AsteriskVersion

from twisted.internet import reactor, protocol, defer, utils, error

logger = logging.getLogger(__name__)

class AsteriskCliCommand():
    """
    Class that manages an Asterisk CLI command.
    """

    def __init__(self, host, cmd):
        """ Create a new Asterisk CLI Protocol instance

        This class wraps an Asterisk instance that executes a CLI command
        against another instance of Asterisk.

        Keyword Arguments:
        host    The host this CLI instance will connect to
        cmd     List of command arguments to spawn.  The first argument must be
        the location of the Asterisk executable; each subsequent argument should define
        the CLI command to run and the instance of Asterisk to run it against.
        """
        self.host = host
        self.__cmd = cmd
        self.cli_cmd = cmd[4]
        self.exitcode = -1
        self.output = ""
        self.err = ""

    def execute(self):
        """ Execute the CLI command.

        Returns a deferred that will be called when the operation completes.  The
        parameter to the deferred is this object.
        """
        def __cli_output_callback(result):
            """ Callback from getProcessOutputAndValue """
            self.__set_properties(result)
            logger.debug("Asterisk CLI %s exited %d" % (self.host, self.exitcode))
            if self.err:
                logger.debug(self.err)
            if self.exitcode:
                self.__deferred.errback(self)
            else:
                self.__deferred.callback(self)

        def __cli_error_callback(result):
            """ Errback from getProcessOutputAndValue """
            self.__set_properties(result)
            logger.warning("Asterisk CLI %s exited %d with error: %s" % (self.host, self.exitcode, self.err))
            if self.err:
                logger.debug(self.err)
            self.__deferred.errback(self)

        self.__deferred = defer.Deferred()
        df = utils.getProcessOutputAndValue(self.__cmd[0], self.__cmd, env=os.environ)
        df.addCallbacks(__cli_output_callback, __cli_error_callback)

        return self.__deferred

    def __set_properties(self, result):
        """ Set the properties based on the result of the getProcessOutputAndValue call """
        out, err, code = result
        self.exitcode = code
        self.output = out
        self.err = err

class AsteriskProtocol(protocol.ProcessProtocol):
    """
    Class that manages an Asterisk instance
    """

    def __init__(self, host, stop_deferred):
        """ Create an AsteriskProtocol object

        Create an AsteriskProtocol object, which manages the interactions with
        the Asterisk process

        Keyword Arguments:
        host - the hostname or address of the Asterisk instance
        stop_deferred - a twisted Deferred object that will be called when the
        process has exited
        """

        self.output = ""
        self.__host = host
        self.exitcode = 0
        self.exited = False
        self.__stop_deferred = stop_deferred

    def outReceived(self, data):
        """ Override of ProcessProtocol.outReceived """
        self.output += data

    def connectionMade(self):
        """ Override of ProcessProtocol.connectionMade """
        logger.debug("Asterisk %s - connection made" % (self.__host))

    def errReceived(self, data):
        """ Override of ProcessProtocol.errReceived """
        logger.warn("Asterisk %s received error: %s" % (self.__host, data))

    def processEnded(self, reason):
        """ Override of ProcessProtocol.processEnded """
        message = ""
        if reason.value and reason.value.exitCode:
            message = "Asterisk %s ended with code %d" % (self.__host, reason.value.exitCode,)
            self.exitcode = reason.value.exitCode
        else:
            message = "Asterisk %s ended " % self.__host
        try:
            # When Asterisk gets itself terminated with a KILL signal, this may (or may not)
            # ever get called, in which case the Asterisk object itself that is terminating
            # this process will attempt to raise the stop deferred.  Prevent calling the
            # object twice.
            if not self.__stop_deferred.called:
                self.__stop_deferred.callback(message)
        except defer.AlreadyCalledError:
            logger.warning("Asterisk %s stop deferred already called" % self.__host)
        self.exited = True

class Asterisk:
    """An instance of Asterisk.

    This class assumes that Asterisk has been installed on the system.  The
    installed version of Asterisk will be mirrored for this dynamically created
    instance.

    Instantiate an Asterisk object to create an instance of Asterisk from
    within python code.  Multiple instances of Asterisk are allowed.  However,
    custom configuration will need to be provided to prevent some modules from
    conflicting with each other.  For example, modules that listen for network
    connections will need to be configured to use different ports on each
    instance of Asterisk.

    To set values for the [options] section in asterisk.conf, provide a
    dictionary to the ast_conf_options parameter.  The key should be the option
    name and the value is the option's value to be written out into
    asterisk.conf.
    """

    """ If AST_TEST_ROOT is unset (the default):

        BINARY = /usr/sbin/asterisk (or found in PATH)
        SOURCE_ETC_DIR = /etc/asterisk
        WORK_DIR = /tmp/asterisk-testsuite

    If it is set:

        BINARY = AST_TEST_ROOT/usr/sbin/asterisk
        SOURCE_ETC_DIR = AST_TEST_ROOT/etc/asterisk
        WORK_DIR = AST_TEST_ROOT/tmp

    This allows you to run tests in a separate environment and without root
    powers.

    Note that AST_TEST_ROOT has to be reasonably short (symlinked in /tmp?) so
    we're not running into the asterisk.ctl AF_UNIX limit.
    """
    localtest_root = os.getenv("AST_TEST_ROOT")
    if localtest_root:
        # Base location of the temporary files created by the testsuite
        test_suite_root = os.path.join(localtest_root, "tmp")
        # The default etc directory for Asterisk
        default_etc_directory = os.path.join(localtest_root, "etc/asterisk")
    else:
        # Base location of the temporary files created by the testsuite
        test_suite_root = "/tmp/asterisk-testsuite"
        # The default etc directory for Asterisk
        default_etc_directory = "/etc/asterisk"

    def __init__(self, base=None, ast_conf_options=None, host="127.0.0.1"):
        """Construct an Asterisk instance.

        Keyword Arguments:
        base -- This is the root of the files associated with this instance of
        Asterisk.  By default, the base is "/tmp/asterisk-testsuite" directory.
        Given a base, it will be appended to the default base directory.

        Example Usage:
        self.asterisk = Asterisk(base="manager/login")
        """
        self.directories = {}
        self.ast_version = AsteriskVersion()
        self.base = Asterisk.test_suite_root
        if base is not None:
            self.base = "%s/%s" % (self.base, base)
        if self.localtest_root:
            self.ast_binary = self.localtest_root + "/usr/sbin/asterisk"
        else:
            self.ast_binary = TestSuiteUtils.which("asterisk") or "/usr/sbin/asterisk"
        self.host = host

        self.__ast_conf_options = ast_conf_options
        self.__directory_structure_made = False
        self.__configs_installed = False
        self.__configs_set_up = False

        """ Find the system installed asterisk.conf """
        ast_confs = [
            os.path.join(self.default_etc_directory, "asterisk.conf"),
            "/usr/local/etc/asterisk/asterisk.conf",
        ]
        self.__ast_conf = None
        for c in ast_confs:
            if os.path.exists(c):
                self.__ast_conf = ConfigFile(c)
                break
        if self.__ast_conf is None:
            logger.error("Unable to locate asterisk.conf file in any known location")
            raise Exception("Unable to locate asterisk.conf file in any known location")

        """ Set which astxxx this instance will be """
        i = 1
        while True:
            if not os.path.isdir("%s/ast%d" % (self.base, i)):
                self.base = "%s/ast%d" % (self.base, i)
                break
            i += 1

        """ Get the Asterisk directories from the Asterisk config file """
        for c in self.__ast_conf.categories:
            if c.name == "directories":
                for (var, val) in c.options:
                    self.directories[var] = val

    def start(self):
        """ Start this instance of Asterisk.

        Returns:
        A deferred object that will be called when Asterisk is fully booted.

        Example Usage:
        asterisk.start()

        Note that calling this will install the default testsuite
        config files, if they have not already been installed
        """

        def __start_asterisk_callback():
            self.processProtocol = AsteriskProtocol(self.host, self.__stop_deferred)
            self.process = reactor.spawnProcess(self.processProtocol,
                                                self.cmd[0],
                                                self.cmd, env=os.environ)
            # Begin the wait fully booted cycle
            self.__start_asterisk_time = time.time()
            reactor.callLater(0, __execute_wait_fully_booted)

        def __execute_wait_fully_booted():
            cli_deferred = self.cli_exec("core waitfullybooted")
            cli_deferred.addCallbacks(__wait_fully_booted_callback, __wait_fully_booted_error)

        def __wait_fully_booted_callback(cli_command):
            """ Callback for CLI command waitfullybooted """
            self.__start_deferred.callback("Successfully started Asterisk %s" % self.host)

        def __wait_fully_booted_error(cli_command):
            """ Errback for CLI command waitfullybooted """
            if time.time() - self.__start_asterisk_time > 5:
                logger.error("Asterisk core waitfullybooted for %s failed" % self.host)
                self.__start_deferred.errback(Exception("Command core waitfullybooted failed"))
            else:
                logger.debug("Asterisk core waitfullybooted failed, attempting again...")
                reactor.callLater(1, __execute_wait_fully_booted)

        self.install_configs(os.getcwd() + "/configs")
        self.__setup_configs()

        self.cmd = [
            self.ast_binary,
            "-f", "-g", "-q", "-m", "-n",
            "-C", "%s" % os.path.join(self.astetcdir, "asterisk.conf")
        ]

        # Make the start/stop deferreds - this method will return
        # the start deferred, and pass the stop deferred to the AsteriskProtocol
        # object.  The stop deferred will be raised when the Asterisk process
        # exits
        self.__start_deferred = defer.Deferred()
        self.__stop_deferred = defer.Deferred()

        # Asterisk will attempt to use built in configuration information if
        # it can't find the configuration files that are being installed - which
        # can happen due to the files being created due to a copy operation.
        # If that happens, the test will fail - wait a second to give
        # Asterisk time to come up fully
        reactor.callLater(1, __start_asterisk_callback)

        return self.__start_deferred

    def stop(self):
        """Stop this instance of Asterisk.

        This function is used to stop this instance of Asterisk.

        Returns:
        A deferred that can be used to detect when Asterisk exits,
        or if it fails to exit.

        Example Usage:
        asterisk.stop()
        """

        def __cancel_stops(reason):
            """ Cancel all stop actions - called when the process exits """
            for token in self.__stop_cancel_tokens:
                try:
                    if token.active():
                        token.cancel()
                except error.AlreadyCalled:
                    # Ignore if we already killed it
                    pass
            return reason

        def __send_stop_gracefully():
            """ Send a core stop gracefully CLI command """
            logger.debug('sending stop gracefully')
            if self.ast_version < AsteriskVersion("1.6.0"):
                cli_deferred = self.cli_exec("stop gracefully")
            else:
                cli_deferred = self.cli_exec("core stop gracefully")
            cli_deferred.addCallbacks(__stop_gracefully_callback,
                __stop_gracefully_error)

        def __stop_gracefully_callback(cli_command):
            """ Callback handler for the core stop gracefully CLI command """
            logger.debug("Successfully stopped Asterisk %s" % self.host)
            reactor.callLater(0, __cancel_stops, None)
            return cli_command

        def __stop_gracefully_error(cli_command):
            """ Errback for the core stop gracefully CLI command """
            logger.warning("Asterisk graceful stop for %s failed" % self.host)
            return cli_command

        def __send_kill():
            """ Check to see if the process is running and kill it with fire """
            try:
                if not self.processProtocol.exited:
                    logger.warning("Sending KILL to Asterisk %s" % self.host)
                    self.process.signalProcess("KILL")
            except error.ProcessExitedAlready:
                # Pass on this
                pass
            # If you kill the process, the ProcessProtocol may never get
            # the note that its dead.  Call the stop callback to notify everyone
            # that we did indeed kill the Asterisk instance.
            try:
                # Attempt to signal the process object that it should lose its
                # connection - it may already be gone however.
                self.process.loseConnection()
            except:
                pass
            try:
                if not self.__stop_deferred.called:
                    self.__stop_deferred.callback("Asterisk %s KILLED" %
                        self.host)
            except defer.AlreadyCalledError:
                logger.warning("Asterisk %s stop deferred already called" %
                    self.host)

        def __process_stopped(reason):
            ''' Generic callback that raises the stopped deferred
            subscribers use to know that the process has exited '''
            self.__stop_deferred.callback(reason)
            return reason

        if self.processProtocol.exited:
            try:
                if not self.__stop_deferred.called:
                    self.__stop_deferred.callback(
                        "Asterisk %s stopped prematurely" % self.host)
            except defer.AlreadyCalledError:
                logger.warning("Asterisk %s stop deferred already called" %
                    self.host)
        else:
            self.__stop_cancel_tokens = []

            # Schedule a kill. If we don't gracefully shut down Asterisk, this
            # will ensure that the test is stopped.
            self.__stop_cancel_tokens.append(reactor.callLater(10, __send_kill))

            # Start by asking to stop gracefully.
            __send_stop_gracefully()

            self.__stop_deferred.addCallback(__cancel_stops)

        return self.__stop_deferred

    def install_configs(self, cfg_path):
        """Installs all files located in the configuration directory for this
        instance of Asterisk.

        By default, the configuration used will be whatever is found in the
        system install of Asterisk.  However, custom configuration files to be
        used only by this instance can be provided via this API call.

        Keyword Arguments:
        cfg_path -- This argument must be the path to the configuration directory
        to be installed into this instance of Asterisk. Only top-level files will
        be installed, sub directories will be ignored.

        Example Usage:
        asterisk.install_configs("tests/my-cool-test/configs")

        Note that this will install the default testsuite config files,
        if they have not already been installed.
        """

        self.__make_directory_structure()

        if self.__configs_installed and cfg_path == ("%s/configs" % os.getcwd()):
            return

        if not self.__configs_installed and cfg_path != ("%s/configs" % os.getcwd()):
            """ Do a one-time installation of the base configs """
            self.install_configs("%s/configs" % os.getcwd())
            self.__configs_installed = True

        if not os.access(cfg_path, os.F_OK):
            return

        for f in os.listdir(cfg_path):
            target = "%s/%s" % (cfg_path, f)
            if os.path.isfile(target):
                self.install_config(target)

    def install_config(self, cfg_path, target_filename=None):
        """Install a custom configuration file for this instance of Asterisk.

        By default, the configuration used will be whatever is found in the
        system install of Asterisk.  However, custom configuration files to be
        used only by this instance can be provided via this API call.

        Note: If a sub-directory is found to have the same name as the running
        instance, install_config() will use the sub-directories version in place
        of the top-level version.

        For example, testsuite is running a test against 1.4 (branch-1.4):

            configs/manager.conf
            configs/sip.conf
            configs/branch-1.4/sip.conf

        Because the sip.conf file exists in the branch-1.4 directory, it will
        be used in place of the top-level sip.conf.  As for the manager.conf
        file, because it does not exists in the branch-1.4 direcory, the
        top-level manager.conf will be used.

        Keyword Arguments:
        cfg_path -- This argument must be the path to the configuration file
        to be installed into the directory tree for this instance of Asterisk.
        target_filename -- If this argument is specified, the config file
        provided will be installed with this filename in the Asterisk etc
        directory. Use this if the file for cfg_path doesn't match the name of
        the configuration needed by Asterisk.

        Example Usage:
        asterisk.install_config("tests/my-cool-test/configs/manager.conf")
        asterisk.install_config("tests/my-cool-test/replacement_manager_config.conf", target_filename = "manager.conf")
        """

        self.__make_directory_structure()

        if not os.path.exists(cfg_path):
            logger.error("Config file '%s' does not exist" % cfg_path)
            return

        tmp = "%s/%s/%s" % (os.path.dirname(cfg_path), self.ast_version.branch, os.path.basename(cfg_path))
        if os.path.exists(tmp):
            cfg_path = tmp

        if (target_filename):
            target_path = os.path.join(self.astetcdir, target_filename)
        else:
            target_path = os.path.join(self.astetcdir, os.path.basename(cfg_path))

        if os.path.exists(target_path):
            os.remove(target_path)
        try:
            shutil.copyfile(cfg_path, target_path)
        except shutil.Error:
            logger.warn("'%s' and '%s' are the same file" % (cfg_path, target_path))
        except IOError:
            logger.warn("The destination is not writable '%s'" % target_path)

    def overwrite_file(self, path, filename, values):
        target_filename = os.path.join(self.astetcdir, filename)

        if not os.path.exists(target_filename):
            logger.error("File '%s' does not exists" % filename)
            return
        try:
            f = open(target_filename, "w")
        except IOError:
            logger.error("Failed to open %s" % target_filename)
            return
        except:
            logger.error("Unexpected error: %s" % sys.exc_info()[0])
            return

        for (var, val) in values:
            f.write('%s = %s\n' % (var, val))

        f.close()

    def cli_originate(self, argstr, blocking=True):
        """Starts a call from the CLI and links it to an application or
        context.

        Must pass a valid argument string in the following form:

        <tech/data> application <appname> appdata
        <tech/data> extension <exten>@<context>

        If no context is specified, the 'default' context will be
        used. If no extension is given, the 's' extension will be used.

        Keyword Arguments:
        blocking -- UNUSED. This used to specify that we should block until the
        CLI command finished executing.  When the Asterisk process was turned
        over to twisted, that's no longer the case.  The keyword argument
        was kept merely for backwards compliance; callers should *not* expect
        their calls to block.

        Returns:
        A deferred object that can be used to listen for command completion

        Example Usage:
        asterisk.originate("Local/a_exten@context extension b_exten@context")
        """

        args = argstr.split()
        raise_error = False
        if len(args) != 3 and len(args) != 4:
            raise_error = True
            logger.error("Wrong number of arguments.")
        if args[1] != "extension" and args[1] != "application":
            raise_error = True
            logger.error('2nd argument must be "extension" or "application"')
        if args[0].find("/") == -1:
            raise_error = True
            logger.error('Channel dial string must be in the form "tech/data".')
        if raise_error is True:
            raise Exception("Cannot originate call!\n"
                "Argument string must be in one of these forms:\n"
                "<tech/data> application <appname> appdata\n"
                "<tech/data> extension <exten>@<context>")

        if self.ast_version < AsteriskVersion("1.6.2"):
            return self.cli_exec("originate %s" % argstr, blocking=blocking)
        else:
            return self.cli_exec("channel originate %s" % argstr, blocking=blocking)

    def cli_exec(self, cli_cmd, blocking=True):
        """Execute a CLI command on this instance of Asterisk.

        Keyword Arguments:
        cli_cmd -- The command to execute.
        blocking -- UNUSED. This used to specify that we should block until the
        CLI command finished executing.  When the Asterisk process was turned
        over to twisted, that's no longer the case.  The keyword argument
        was kept merely for backwards compliance; callers should *not* expect
        their calls to block.

        Returns:
        A deferred object that will be signaled when the process has exited

        Example Usage:
        asterisk.cli_exec("core set verbose 10")
        """
        cmd = [
            self.ast_binary,
            "-C", "%s" % os.path.join(self.astetcdir, "asterisk.conf"),
            "-rx", "%s" % cli_cmd
        ]
        logger.debug("Executing %s ..." % cmd)

        cliProtocol = AsteriskCliCommand(self.host, cmd)
        return cliProtocol.execute()

    def __make_directory_structure(self):
        """ Mirror system directory structure """

        if self.__directory_structure_made:
            return

        """ Make the directory structure if not available """
        if not os.path.exists(self.base):
            os.makedirs(self.base)

        dir_cat = None
        for c in self.__ast_conf.categories:
            if c.name == "directories":
                dir_cat = c
        if dir_cat is None:
            logger.error("Unable to discover dir layout from asterisk.conf")
            raise Exception("Unable to discover dir layout from asterisk.conf")

        self.__gen_ast_conf(self.__ast_conf, dir_cat, self.__ast_conf_options)

        # Cache mirrored dirs to speed up creation. Generally you'll have
        # /var/lib/asterisk for more than one dir_cat option, and that happens
        # to be the largest dir too (with lots of sounds).
        cache = set()
        for (var, val) in dir_cat.options:
            # We cannot simply skip ``val`` here if we already processed it.
            # Some dirs are exempt from copying, based on ``var``.
            self.__mirror_dir(var, val, cache)

        self.__directory_structure_made = True

    def __setup_configs(self):
        """
        Perform any post-installation manipulation of the config
        files
        """
        if self.__configs_set_up:
            return
        self.__setup_manager_conf()
        self.__configs_set_up = True

    def __setup_manager_conf(self):
        values = []

        if self.host == '127.0.0.1':
            return

        values.append(['bindaddr', self.host])

        self.overwrite_file(self.directories['astetcdir'],
            "manager.general.conf.inc", values)

    def __gen_ast_conf(self, ast_conf, dir_cat, ast_conf_options):
        for (var, val) in dir_cat.options:
            if var == "astetcdir":
                self.astetcdir = "%s%s" % (self.base, val)
                os.makedirs(self.astetcdir)

        local_ast_conf_path = os.path.join(self.astetcdir, "asterisk.conf")

        try:
            f = open(local_ast_conf_path, "w")
        except IOError:
            logger.error("Failed to open %s" % local_ast_conf_path)
            return
        except:
            logger.error("Unexpected error: %s" % sys.exc_info()[0])
            return

        for c in self.__ast_conf.categories:
            f.write("[%s]\n" % c.name)
            if c.name == "directories":
                for (var, val) in c.options:
                    f.write("%s = %s%s\n" % (var, self.base, val))
            elif c.name == "options":
                f.write("#include \"%s/asterisk.options.conf.inc\"\n" %
                        (self.astetcdir))
                if ast_conf_options:
                    for (var, val) in ast_conf_options.iteritems():
                        f.write("%s = %s\n" % (var, val))
                for (var, val) in c.options:
                    if not ast_conf_options or var not in ast_conf_options:
                        f.write("%s = %s\n" % (var, val))
            else:
                for (var, val) in c.options:
                    f.write("%s = %s\n" % (var, val))
            f.write("\n")

        f.close()

    def __mirror_dir(self, ast_dir_name, ast_dir_path, cache):
        self.__makedirs(ast_dir_path)
        dirs_only = ["astrundir", "astlogdir", "astspooldir"]
        if ast_dir_name in dirs_only:
            return
        blacklist = ["astdb", "astdb.sqlite3"]

        if ast_dir_path in cache:
            return
        cache.add(ast_dir_path)

        # If we're running with a separate localroot, the paths in
        # AST_TEST_ROOT/etc/asterisk/asterisk.conf are still short; e.g.
        # /etc/asterisk. We suffix AST_TEST_ROOT here to get the real source
        # dir.
        if self.localtest_root:
            ast_real_dir_path = self.localtest_root + ast_dir_path
        else:
            ast_real_dir_path = ast_dir_path

        for dirname, dirnames, filenames in os.walk(ast_real_dir_path):
            assert dirname[0] == "/"

            for filename in filenames:
                # Shorten the dirname for inclusion into the new path.
                short_dirname = dirname
                if self.localtest_root:
                    short_dirname = dirname[len(self.localtest_root):]

                assert short_dirname[0] == "/"
                target = "%s/%s/%s" % (self.base, short_dirname[1:], filename)
                if os.path.lexists(target) or filename in blacklist:
                    continue

                os.symlink(os.path.join(ast_dir_path, dirname, filename),
                           target)

    def __makedirs(self, ast_dir_path):
        # If we're running with a separate localroot, the paths in
        # AST_TEST_ROOT/etc/asterisk/asterisk.conf are still short; e.g.
        # /etc/asterisk. We suffix AST_TEST_ROOT here to get the real source
        # dir.
        if self.localtest_root:
            ast_real_dir_path = self.localtest_root + ast_dir_path
        else:
            ast_real_dir_path = ast_dir_path

        target_dir = "%s%s" % (self.base, ast_dir_path)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)

        for dirname, dirnames, filenames in os.walk(ast_real_dir_path):
            # Shorten the dirname for inclusion into the new path.
            short_dirname = dirname
            if self.localtest_root:
                short_dirname = dirname[len(self.localtest_root):]

            for d in dirnames:
                self.__makedirs(os.path.join(target_dir, short_dirname, d))


# vim: set ts=8 sw=4 sts=4 et ai tw=79:
