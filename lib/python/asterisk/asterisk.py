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
            logger.debug(self.output)
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
            logger.debug(self.output)
            if self.err:
                logger.debug(self.err)
            self.__deferred.errback(self)

        self.__deferred = defer.Deferred()
        df = utils.getProcessOutputAndValue(self.__cmd[0], self.__cmd)
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
        logger.debug("Asterisk %s received: %s" % (self.__host, data))
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

    """ The base location of the temporary files created by the testsuite """
    test_suite_root = "/tmp/asterisk-testsuite"

    """ The default etc directory for Asterisk """
    asterisk_etc_directory = "/etc/asterisk"

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
        self.astetcdir = Asterisk.asterisk_etc_directory
        self.ast_binary = TestSuiteUtils.which("asterisk") or "/usr/sbin/asterisk"
        self.host = host

        self.__ast_conf_options = ast_conf_options
        self.__directory_structure_made = False
        self.__configs_installed = False
        self.__configs_set_up = False

        """ Find the system installed asterisk.conf """
        ast_confs = [
                "/etc/asterisk/asterisk.conf",
                "/usr/local/etc/asterisk/asterisk.conf"
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

        def __wait_fully_booted_callback(cli_command):
            """ Callback for CLI command waitfullybooted """
            self.__start_deferred.callback("Successfully started Asterisk %s" % self.host)

        def __wait_fully_booted_error(cli_command):
            """ Errback for CLI command waitfullybooted """
            if time.time() - self.__start_asterisk_time > 5:
                logger.error("Asterisk core waitfullybooted for %s failed" % self.host)
                self.__start_deferred.errback("Command core waitfullybooted failed")
            else:
                logger.debug("Asterisk core waitfullybooted failed, attempting again...")
                cli_deferred = self.cli_exec("core waitfullybooted")
                cli_deferred.addCallbacks(__wait_fully_booted_callback, __wait_fully_booted_error)

        self.install_configs(os.getcwd() + "/configs")
        self.__setup_configs()

        cmd = [
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
        self.processProtocol = AsteriskProtocol(self.host, self.__stop_deferred)
        self.process = reactor.spawnProcess(self.processProtocol, cmd[0], cmd)

        # Begin the wait fully booted cycle
        self.__start_asterisk_time = time.time()
        cli_deferred = self.cli_exec("core waitfullybooted")
        cli_deferred.addCallbacks(__wait_fully_booted_callback, __wait_fully_booted_error)
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

        def __send_stop_gracefully():
            """ Send a core stop gracefully CLI command """
            if self.ast_version < AsteriskVersion("1.6.0"):
                cli_deferred = self.cli_exec("stop gracefully")
            else:
                cli_deferred = self.cli_exec("core stop gracefully")
            cli_deferred.addCallbacks(__stop_gracefully_callback, __stop_gracefully_error)

        def __stop_gracefully_callback(cli_command):
            """ Callback handler for the core stop gracefully CLI command """
            logger.debug("Successfully stopped Asterisk %s" % self.host)
            self.__stop_attempts = 0

        def __stop_gracefully_error(cli_command):
            """ Errback for the core stop gracefully CLI command """
            if self.__stop_attempts > 5:
                self.__stop_attempts = 0
                logger.warning("Asterisk graceful stop for %s failed" % self.host)
            else:
                logger.debug("Asterisk graceful stop failed, attempting again...")
                self.__stop_attempts += 1
                __send_stop_gracefully()

        def __send_stop_now():
            """ Send a core stop now CLI command """
            if self.ast_version < AsteriskVersion("1.6.0"):
                cli_deferred = self.cli_exec("stop now")
            else:
                cli_deferred = self.cli_exec("core stop now")
            if cli_deferred:
                cli_deferred.addCallbacks(__stop_now_callback, __stop_now_error)

        def __stop_now_callback(cli_command):
            """ Callback handler for the core stop now CLI command """
            logger.debug("Successfully stopped Asterisk %s" % self.host)
            self.__stop_attempts = 0

        def __stop_now_error(cli_command):
            """ Errback handler for the core stop now CLI command """
            if self.__stop_attempts > 5:
                self.__stop_attempts = 0
                logger.warning("Asterisk graceful stop for %s failed" % self.host)
            else:
                logger.debug("Asterisk stop now failed, attempting again...")
                self.__stop_attempts += 1
                cli_deferred = __send_stop_now()
                if cli_deferred:
                    cli_deferred.addCallbacks(__stop_now_callback, __stop_now_error)

        def __send_term():
            """ Send a TERM signal to the Asterisk instance """
            try:
                logger.info("Sending TERM to Asterisk %s" % self.host)
                self.process.signalProcess("TERM")
            except error.ProcessExitedAlready:
                # Probably that we sent a signal to a process that was already
                # dead.  Just ignore it.
                pass

        def __send_kill():
            """ Check to see if the process is running and kill it with fire """
            try:
                if not self.processProtocol.exited:
                    logger.info("Sending KILL to Asterisk %s" % self.host)
                    self.process.signalProcess("KILL")
            except error.ProcessExitedAlready:
                # Pass on this
                pass
            # If you kill the process, the ProcessProtocol may never get the note
            # that its dead.  Call the stop callback to notify everyone that we did
            # indeed kill the Asterisk instance.
            try:
                # Attempt to signal the process object that it should lose its
                # connection - it may already be gone however.
                self.process.loseConnection()
            except:
                pass
            try:
                if not self.__stop_deferred.called:
                    self.__stop_deferred.callback("Asterisk %s KILLED" % self.host)
            except defer.AlreadyCalledError:
                logger.warning("Asterisk %s stop deferred already called" % self.host)

        def __cancel_stops(reason):
            """ Cancel all stop actions - called when the process exits """
            for token in self.__stop_cancel_tokens:
                try:
                    if token.active():
                        token.cancel()
                except error.AlreadyCalled:
                    # If we're canceling something that's already been called, move on
                    pass
            return reason

        self.__stop_cancel_tokens = []
        self.__stop_attempts = 0
        # Start by asking to stop gracefully.
        __send_stop_gracefully()

        # Schedule progressively more aggressive mechanisms of stopping Asterisk.  If any
        # stop mechanism succeeds, all are canceled
        self.__stop_cancel_tokens.append(reactor.callLater(5, __send_stop_now))
        self.__stop_cancel_tokens.append(reactor.callLater(10, __send_term))
        self.__stop_cancel_tokens.append(reactor.callLater(15, __send_kill))

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

        for f in os.listdir(cfg_path):
            target = "%s/%s" % (cfg_path, f)
            if os.path.isfile(target):
                self.install_config(target)

    def install_config(self, cfg_path):
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

        Example Usage:
        asterisk.install_config("tests/my-cool-test/configs/manager.conf")
        """

        self.__make_directory_structure()

        if not os.path.exists(cfg_path):
            logger.error("Config file '%s' does not exist" % cfg_path)
            return

        tmp = "%s/%s/%s" % (os.path.dirname(cfg_path), self.ast_version.branch, os.path.basename(cfg_path))
        if os.path.exists(tmp):
            cfg_path = tmp
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
        blocking -- This used to specify that we should block until the
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
            raise Exception, "Cannot originate call!\n\
            Argument string must be in one of these forms:\n\
            <tech/data> application <appname> appdata\n\
            <tech/data> extension <exten>@<context>"

        if self.ast_version < AsteriskVersion("1.6.2"):
            return self.cli_exec("originate %s" % argstr, blocking=blocking)
        else:
            return self.cli_exec("channel originate %s" % argstr, blocking=blocking)

    def cli_exec(self, cli_cmd, blocking=True, warn_on_fail=True):
        """Execute a CLI command on this instance of Asterisk.

        Keyword Arguments:
        cli_cmd -- The command to execute.
        blocking -- This used to specify that we should block until the
        CLI command finished executing.  When the Asterisk process was turned
        over to twisted, that's no longer the case.  The keyword argument
        was kept merely for backwards compliance; callers should *not* expect
        their calls to block.

        Returns:
        A deferred object that will be signaled when the process has exited

        Example Usage:
        asterisk.cli_exec("core set verbose 10")
        """
        # Downplay warnings if the caller requests it
        warn = (logger.debug, logger.warn)[bool(warn_on_fail)]

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
        for (var, val) in dir_cat.options:
            self.__mirror_dir(var, val)

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

    def __mirror_dir(self, ast_dir_name, ast_dir_path):
        self.__makedirs(ast_dir_path)
        dirs_only = [ "astrundir", "astlogdir", "astspooldir" ]
        if ast_dir_name in dirs_only:
            return
        blacklist = [ "astdb", "astdb.sqlite3" ]
        for dirname, dirnames, filenames in os.walk(ast_dir_path):
            for filename in filenames:
                target = "%s/%s" % (self.base, os.path.join(ast_dir_path,
                                    dirname, filename))
                if os.path.exists(target) or filename in blacklist:
                    continue
                os.symlink(os.path.join(ast_dir_path, dirname, filename),
                           target)

    def __makedirs(self, ast_dir_path):
        target_dir = "%s%s" % (self.base, ast_dir_path)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir)
        for dirname, dirnames, filenames in os.walk(ast_dir_path):
            for d in dirnames:
                self.__makedirs(os.path.join(target_dir, dirname, d))
