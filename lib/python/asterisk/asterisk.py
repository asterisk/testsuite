"""Asterisk Instances in Python.

This module provides an interface for creating instances of Asterisk
from within python code.

Copyright (C) 2010-2013, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import time
import shutil
import logging
import fileinput
import polyfill

from . import test_suite_utils

from .config import ConfigFile

from twisted.internet import reactor, protocol, defer, utils, error
from twisted.python.failure import Failure

REMOTE_ERROR = None
try:
    from twisted.python.filepath import FilePath
    from twisted.internet.endpoints import UNIXClientEndpoint
    from twisted.conch.ssh.keys import Key
    from twisted.conch.client.knownhosts import KnownHostsFile
    from twisted.conch.endpoints import SSHCommandClientEndpoint
    from twisted.internet.error import ProcessTerminated
except ImportError as ie:
    # We cache any import errors here, as there's no point in bothering
    # things if we don't need the SSH connection to a remote Asterisk instance
    REMOTE_ERROR = ie

from .pluggable_registry import PLUGGABLE_EVENT_REGISTRY,\
    PLUGGABLE_ACTION_REGISTRY, var_replace


LOGGER = logging.getLogger(__name__)

class AsteriskRemoteProtocol(protocol.Protocol):
    """Class that acts as a remote protocol to Asterisk"""

    def connectionMade(self):
        """Called on connect"""
        LOGGER.debug('Connection made to remote Asterisk instance')
        self.output = ''
        self.finished = defer.Deferred()

    def dataReceived(self, data):
        """Called when we receive data back"""
        LOGGER.debug(data)
        self.output += data.decode('utf-8', 'ignore')

    def connectionLost(self, reason):
        """Called when the connect is lost"""
        if reason.type == ProcessTerminated:
            self.output += reason.getErrorMessage()
            self.finished.errback(self)
        else:
            self.finished.callback(self)


class AsteriskRemoteCliCommand(object):
    """Class that attempts to manipulate a remote Asterisk CLI"""

    def __init__(self, remote_config, cmd):
        """Create a new remote Astrisk CLI Protocol instance

        Keyword Arguments:
        remote_config The parameters configuring this remote CLI command
        cmd           The CLI command to run
        """
        if REMOTE_ERROR:
            raise REMOTE_ERROR

        self.exitcode = -1
        self.output = ""
        self.err = ""

        self.config = remote_config
        self.cmd = cmd
        self.keys = []

        identity = self.config.get('identity')
        if identity:
            key_path = os.path.expanduser(identity)
            if os.path.exists(key_path):
                passphrase = self.config.get('passphrase')
                self.keys.append(Key.fromFile(key_path, passphrase=passphrase))

        known_hosts_file = self.config.get('known_hosts', '~/.ssh/known_hosts')
        known_hosts_path = FilePath(os.path.expanduser(known_hosts_file))
        if known_hosts_path.exists():
            self.known_hosts = KnownHostsFile.fromPath(known_hosts_path)
        else:
            self.known_hosts = None

        no_agent = self.config.get('no-agent')
        if no_agent or 'SSH_AUTH_SOCK' not in os.environ:
            self.agent_endpoint = None
        else:
            self.agent_endpoint = UNIXClientEndpoint(reactor,
                                                     os.environ['SSH_AUTH_SOCK'])

    def execute(self):
        """Execute the CLI command"""

        cmd = " ".join(self.cmd)
        LOGGER.debug('Executing {0}'.format(cmd))
        endpoint = SSHCommandClientEndpoint.newConnection(reactor,
            b"{0}".format(cmd), self.config.get('username'),
            self.config.get('host'),
            port=self.config.get('port', 22),
            password=self.config.get('passsword'),
            agentEndpoint=self.agent_endpoint,
            keys=self.keys,
            knownHosts=self.known_hosts)
        factory = protocol.Factory()
        factory.protocol = AsteriskRemoteProtocol

        def _nominal(param):
            self.exitcode = 0
            self.output = param.output
            self.err = self.output
            LOGGER.debug('Remote Asterisk process completed successfully')
            return self

        def _error(param):
            self.exitcode = -1
            self.output = param.value.output
            self.err = self.output
            LOGGER.warning('Remote Asterisk process failed: {0}'.format(self.err))
            return Failure(self)

        deferred = endpoint.connect(factory)
        deferred.addCallback(lambda proto: proto.finished)
        deferred.addCallbacks(_nominal, _error)
        return deferred


class AsteriskCliCommand(object):
    """Class that manages an Asterisk CLI command."""

    def __init__(self, host, cmd):
        """Create a new Asterisk CLI Protocol instance

        This class wraps an Asterisk instance that executes a CLI command
        against another instance of Asterisk.

        Keyword Arguments:
        host    The host this CLI instance will connect to
        cmd     List of command arguments to spawn.  The first argument must be
                the location of the Asterisk executable; each subsequent
                argument should define the CLI command to run and the instance
                of Asterisk to run it against.
        """
        self.host = host
        self._cmd = cmd
        self.cli_cmd = cmd[4]
        self.exitcode = -1
        self.output = ""
        self.err = ""
        self._deferred = None

    def execute(self):
        """Execute the CLI command.

        Returns a deferred that will be called when the operation completes. The
        parameter to the deferred is this object.
        """
        def __cli_output_callback(result):
            """Callback from getProcessOutputAndValue"""
            self._set_properties(result)
            LOGGER.debug("Asterisk CLI %s exited %d" %
                         (self.host, self.exitcode))
            if self.err:
                LOGGER.debug(self.err)
            if self.exitcode:
                self._deferred.errback(self)
            else:
                self._deferred.callback(self)

        def __cli_error_callback(result):
            """Errback from getProcessOutputAndValue"""
            self._set_properties(result.value)
            LOGGER.warning("Asterisk CLI %s exited %d with error: %s" %
                           (self.host, self.exitcode, self.err))
            if self.err:
                LOGGER.debug(self.err)
            self._deferred.errback(self)

        self._deferred = defer.Deferred()
        deferred = utils.getProcessOutputAndValue(self._cmd[0],
                                                  self._cmd[1:],
                                                  env=os.environ)
        deferred.addCallbacks(callback=__cli_output_callback,
                              errback=__cli_error_callback,)

        return self._deferred

    def _set_properties(self, result):
        """Set the properties based on the result of the
        getProcessOutputAndValue call"""
        bintxt, self.err, self.exitcode = result
        self.output = bintxt.decode('utf-8', 'ignore')


class AsteriskProtocol(protocol.ProcessProtocol):
    """Class that manages an Asterisk instance"""

    def __init__(self, host, stop_deferred):
        """Create an AsteriskProtocol object

        Create an AsteriskProtocol object, which manages the interactions with
        the Asterisk process

        Keyword Arguments:
        host - the hostname or address of the Asterisk instance
        stop_deferred - a twisted Deferred object that will be called when the
        process has exited
        """

        self.output = ""
        self._host = host
        self.exitcode = 0
        self.exited = False
        self._stop_deferred = stop_deferred

    def outReceived(self, data):
        """Override of ProcessProtocol.outReceived"""
        self.output += data.decode('utf-8', 'ignore')

    def connectionMade(self):
        """Override of ProcessProtocol.connectionMade"""
        LOGGER.debug("Asterisk %s - connection made" % (self._host))

    def errReceived(self, data):
        """Override of ProcessProtocol.errReceived"""
        LOGGER.warn("Asterisk %s received error: %s" % (self._host, data))

    def processEnded(self, reason):
        """Override of ProcessProtocol.processEnded"""
        message = ""
        if reason.value and reason.value.exitCode:
            message = "Asterisk %s ended with code %d" % \
                      (self._host, reason.value.exitCode,)
            self.exitcode = reason.value.exitCode
        else:
            message = "Asterisk %s ended " % self._host
        try:
            # When Asterisk gets itself terminated with a KILL signal, this may
            # (or may not) ever get called, in which case the Asterisk object
            # itself that is terminating this process will attempt to raise the
            # stop deferred.  Prevent calling the object twice.
            if not self._stop_deferred.called:
                self._stop_deferred.callback(message)
        except defer.AlreadyCalledError:
            LOGGER.warning("Asterisk %s stop deferred already called" %
                           self._host)
        self.exited = True

class Asterisk(object):
    """An instance of Asterisk.

    This class has two modes of operation, depending on how it is instantiated.
    In the first, the class assumes that Asterisk has been installed on the system.
    The installed version of Asterisk will be mirrored for this dynamically created
    instance. The following applies to instances of Asterisk controlled locally.

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

    In the second mode of operation, this class provides a facade over some
    remote running instance of Asterisk. In this case, the configuration of
    that instance of Asterisk is assumed to be set, and any properties passed
    to this class that may attempt to configure the remote instance of Asterisk
    are ignored. Instead, a block of configuration is provided to this class
    that defines how it should connect (over SSH) to the remote instance.
    Users of this class can manipulate the remote instance using CLI commands
    in the same fashion as if the instance were local.

    If AST_TEST_ROOT is unset (the default):

        BINARY = /usr/sbin/asterisk (or found in PATH)
        SOURCE_ETC_DIR = /etc/asterisk
        If AST_WORK_DIR is unset (the default):
            WORK_DIR = /tmp/asterisk-testsuite
        If it is set:
            WORK_DIR = AST_WORK_DIR/asterisk-testsuite

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
        best_tmp = os.getenv("AST_WORK_DIR")
        if not best_tmp:
            # select tmp path with most available space
            best_tmp = sorted(['/tmp', '/var/tmp'],
                              key=lambda path: os.statvfs(path).f_bavail,
                              reverse=True)[0]

        # Base location of the temporary files created by the testsuite
        test_suite_root = best_tmp + "/asterisk-testsuite"
        # The default etc directory for Asterisk
        default_etc_directory = "/etc/asterisk"

    def __init__(self, base=None, ast_conf_options=None, host="127.0.0.1",
                 remote_config=None, test_config=None):
        """Construct an Asterisk instance.

        Keyword Arguments:
        base -- This is the root of the files associated with this instance of
                Asterisk. By default, the base is "/tmp/asterisk-testsuite"
                directory. Given a base, it will be appended to the default base
                directory.
        ast_conf_options -- Configuration overrides for asterisk.conf.
        host -- The IP address the Asterisk instance runs on
        remote_config -- Configuration section that defines this as a remote
                         Asterisk instance. If provided, base and
                         ast_conf_options are generally ignored, and the
                         Asterisk instance's configuration is treated as
                         immutable on some remote machine defined by 'host'
        test_config -- yaml loaded object containing config information

        Example Usage:
        self.asterisk = Asterisk(base="manager/login")
        """
        self._start_deferred = None
        self._stop_deferred = None
        self._stop_cancel_tokens = []
        self.directories = {}
        self.protocol = None
        self.process = None
        self.astetcdir = ""
        self.original_astmoddir = ""
        self.remote_config = remote_config
        self.memcheck_delay_stop = 0
        self.instance_id = 0
        if test_config is not None and 'memcheck-delay-stop' in test_config:
            self.memcheck_delay_stop = test_config['memcheck-delay-stop'] or 0

        valgrind_env = os.getenv("VALGRIND_ENABLE") or ""
        self.valgrind_enabled = True if "true" in valgrind_env else False

        if base is not None:
            self.base = base
        else:
            self.base = Asterisk.test_suite_root
        if self.localtest_root:
            self.ast_binary = self.localtest_root + "/usr/sbin/asterisk"
        else:
            ast_binary = test_suite_utils.which("asterisk")
            self.ast_binary = ast_binary or "/usr/sbin/asterisk"
        self.host = host

        self._ast_conf_options = ast_conf_options

        if self.remote_config:
            # Pretend as if we made the structure
            self._directory_structure_made = True
            self._configs_installed = True
            self._configs_set_up = True

            # And assume we've got /etc/asterisk/ where we expect it to be
            self.astetcdir = "/etc/asterisk"
        else:
            self._directory_structure_made = False
            self._configs_installed = False
            self._configs_set_up = False

            # Find the system installed asterisk.conf
            ast_confs = [
                os.path.join(self.default_etc_directory, "asterisk.conf"),
                "/usr/local/etc/asterisk/asterisk.conf",
            ]
            self._ast_conf = None
            for config in ast_confs:
                if os.path.exists(config):
                    self._ast_conf = ConfigFile(config)
                    break
            if self._ast_conf is None:
                msg = "Unable to locate asterisk.conf in any known location"
                LOGGER.error(msg)
                raise Exception(msg)

            # Set which astxxx this instance will be
            i = 1
            while True:
                if not os.path.isdir("%s/ast%d" % (self.base, i)):
                    self.base = "%s/ast%d" % (self.base, i)
                    self.instance_id = i;
                    break
                i += 1

            # Get the Asterisk directories from the Asterisk config file
            for cat in self._ast_conf.categories:
                if cat.name == "directories":
                    for (var, val) in cat.options:
                        self.directories[var] = val

            # self.original_astmoddir is for dependency checking only
            if "astmoddir" in self.directories:
                if self.localtest_root:
                    self.original_astmoddir = "%s%s" % (
                        self.localtest_root, self.directories["astmoddir"])
                else:
                    self.original_astmoddir = self.directories["astmoddir"]

    def start(self, deps=None):
        """Start this instance of Asterisk.

        Returns:
        A deferred object that will be called when Asterisk is fully booted.

        Example Usage:
        asterisk.start()

        Note that calling this will install the default testsuite
        config files, if they have not already been installed
        """

        def __start_asterisk_callback(cmd):
            """Begin the Asterisk startup cycle"""

            self.__start_asterisk_time = time.time()

            if self.remote_config:
                reactor.callLater(0, __execute_wait_fully_booted)
                return

            self.protocol = AsteriskProtocol(self.host, self._stop_deferred)
            self.process = reactor.spawnProcess(self.protocol,
                                                cmd[0],
                                                cmd, env=os.environ)
            # Begin the wait fully booted cycle
            reactor.callLater(1, __execute_wait_fully_booted)

        def __execute_wait_fully_booted():
            """Send the CLI command waitfullybooted"""

            cli_deferred = self.cli_exec("core waitfullybooted")
            cli_deferred.addCallbacks(__wait_fully_booted_callback,
                                      __wait_fully_booted_error)

        def __wait_fully_booted_callback(cli_command):
            """Callback for CLI command waitfullybooted"""

            if "Asterisk has fully booted" in cli_command.output:
                msg = "Successfully started Asterisk %s" % self.host
                self._start_deferred.callback(msg)
            else:
                LOGGER.debug("Asterisk core waitfullybooted failed " +
                             "with output '%s', attempting again..." %
                             cli_command.output)
                reactor.callLater(1, __execute_wait_fully_booted)
            return cli_command

        def __wait_fully_booted_error(cli_command):
            """Errback for CLI command waitfullybooted"""

            timeout = 90 if self.valgrind_enabled else 45
            if time.time() - self.__start_asterisk_time > timeout:
                msg = "Asterisk core waitfullybooted for %s failed" % self.host
                LOGGER.error(msg)
                self._start_deferred.errback(Exception(msg))
            else:
                msg = "Asterisk core waitfullybooted failed, attempting again"
                LOGGER.debug(msg)
                reactor.callLater(1, __execute_wait_fully_booted)
            return cli_command

        self.install_configs(os.getcwd() + "/configs", deps)
        self._setup_configs()

        cmd_prefix = []

        if os.getenv("VALGRIND_ENABLE") == "true":
            valgrind_path = test_suite_utils.which('valgrind')
            if valgrind_path:
                # No need to modify this array to add options.  Instead create
                # .valgrindrc in the testsuite root directory.
                cmd_prefix = [
                    valgrind_path,
                    '--xml=yes',
                    '--xml-file=%s' % self.get_path("astlogdir", 'valgrind.xml'),
                    '--xml-user-comment=%s (%s)' % (
                        os.environ['TESTSUITE_ACTIVE_TEST'], self.host)]
                suppression_file = 'contrib/valgrind/suppressions.txt'
                if os.path.exists(suppression_file):
                    cmd_prefix.append('--suppressions=%s' % suppression_file)
            else:
                LOGGER.error('Valgrind not found')

        cmd = cmd_prefix + [
            self.ast_binary,
            "-f", "-g", "-q", "-m", "-n",
            "-C", "%s" % os.path.join(self.astetcdir, "asterisk.conf")
        ]

        # Make the start/stop deferreds - this method will return
        # the start deferred, and pass the stop deferred to the AsteriskProtocol
        # object.  The stop deferred will be raised when the Asterisk process
        # exits
        self._start_deferred = defer.Deferred()
        self._stop_deferred = defer.Deferred()

        # Asterisk will attempt to use built in configuration information if
        # it can't find the configuration files that are being installed - which
        # can happen due to the files being created due to a copy operation.
        # If that happens, the test will fail - wait a second to give
        # Asterisk time to come up fully
        reactor.callLater(0, __start_asterisk_callback, cmd)

        return self._start_deferred

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
            """Cancel all stop actions - called when the process exits"""
            for token in self._stop_cancel_tokens:
                try:
                    if token.active():
                        token.cancel()
                except error.AlreadyCalled:
                    # Ignore if we already killed it
                    pass
            return reason

        def __send_stop_gracefully():
            """Send a core stop gracefully CLI command"""
            LOGGER.debug('sending stop gracefully')
            cli_deferred = self.cli_exec("core stop gracefully")
            cli_deferred.addCallbacks(__stop_gracefully_callback, __stop_gracefully_error)

        def __stop_gracefully_callback(cli_command):
            """Callback handler for the core stop gracefully CLI command"""
            LOGGER.debug("Successfully stopped Asterisk %s" % self.host)
            reactor.callLater(0, __cancel_stops, None)
            return cli_command

        def __stop_gracefully_error(cli_command):
            """Errback for the core stop gracefully CLI command"""
            LOGGER.warning("Asterisk graceful stop for %s failed" % self.host)
            return cli_command

        def __send_kill():
            """Check to see if the process is running and kill it with fire"""
            try:
                if self.process and not self.protocol.exited:
                    LOGGER.warning("Sending KILL to Asterisk %s" % self.host)
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
                if not self._stop_deferred.called:
                    self._stop_deferred.callback("Asterisk %s KILLED" % self.host)
            except defer.AlreadyCalledError:
                LOGGER.warning("Asterisk %s stop deferred already called" % self.host)

        def __process_stopped(reason):
            """Generic callback that raises the stopped deferred subscribers
            use to know that the process has exited"""
            self._stop_deferred.callback(reason)
            return reason

        def __actual_stop():
            # Schedule a kill. If we don't gracefully shut down Asterisk, this
            # will ensure that the test is stopped.
            sched_time = 200 if self.valgrind_enabled else 45

            self._stop_cancel_tokens.append(reactor.callLater(sched_time,
                                            __send_kill))

            # Start by asking to stop gracefully.
            __send_stop_gracefully()

            self._stop_deferred.addCallback(__cancel_stops)

        if not self.process:
            reactor.callLater(0, __process_stopped, None)
        elif self.protocol.exited:
            try:
                if not self._stop_deferred.called:
                    self._stop_deferred.callback(
                        "Asterisk %s stopped prematurely" % self.host)
            except defer.AlreadyCalledError:
                LOGGER.warning("Asterisk %s stop deferred already called" %
                               self.host)
        else:
            delay = 0
            if self.valgrind_enabled or os.path.exists(self.get_path("astlogdir", 'refs')):
                delay = self.memcheck_delay_stop
                if delay != 0:
                    LOGGER.debug("Delaying shutdown by %d seconds" % delay)

            reactor.callLater(delay, __actual_stop)

        return self._stop_deferred

    def get_path(self, astdirkey, *paths):
        """Join paths using the correct prefix for the current instance.

        Keyword Arguments:
        astdirkey This argument must match a directory key from asterisk.conf.
        *paths This is a list of paths to be appended using os.path.join.

        Example Usage:
        asterisk.get_path("astlogdir", "cdr-csv", "Master.csv")
        """

        if not astdirkey in self.directories:
            msg = "Directory '%s' not found in asterisk.conf" % astdirkey
            LOGGER.error(msg)
            raise Exception(msg)

        return os.path.join(self.base + self.directories[astdirkey], *paths)

    def configuration_replace_string(self, value):
        """Replace variables in a string with directory paths"""
        if "<<" not in value:
            return value
        for key in self.directories.keys():
            value = value.replace("<<%s>>" % key,
                              "%s%s" % (self.base, self.directories[key]))
        value = value.replace("<<instanceid>>", str(self.instance_id))
        return value

# Quick little function for doing search and replace in a file used below.
    def _file_replace_string(self, file):
        for line in fileinput.input(file, inplace=1):
            line = self.configuration_replace_string(line)
            sys.stdout.write(line)

    def install_configs(self, cfg_path, deps=None):
        """Installs all files located in the configuration directory for this
        instance of Asterisk.

        By default, the configuration used will be whatever is found in the
        system install of Asterisk.  However, custom configuration files to be
        used only by this instance can be provided via this API call.

        Keyword Arguments:
        cfg_path This argument must be the path to the configuration directory
                 to be installed into this instance of Asterisk. Only top-level
                 files will be installed, sub directories will be ignored.

        Example Usage:
        asterisk.install_configs("tests/my-cool-test/configs")

        Note that this will install the default testsuite config files,
        if they have not already been installed.
        """

        self._make_directory_structure()

        cur_cfg_path = "%s/configs" % os.getcwd()
        if self._configs_installed and cfg_path == cur_cfg_path:
            return

        if not self._configs_installed and cfg_path != cur_cfg_path:
            # Do a one-time installation of the base configs
            self.install_configs("%s/configs" % os.getcwd())
            # the default modules.conf should be installed now, so append
            # conflicts this can be overriden by a test specific modules.conf
            self._append_modules_conf(deps)
            self._configs_installed = True

        if not os.access(cfg_path, os.F_OK):
            return

        for fname in os.listdir(cfg_path):
            target = "%s/%s" % (cfg_path, fname)
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
        asterisk.install_config("tests/my-cool-test/replacement_manager.conf",
                                target_filename="manager.conf")
        """

        self._make_directory_structure()

        if not os.path.exists(cfg_path):
            LOGGER.error("Config file '%s' does not exist" % cfg_path)
            return

        tmp = "%s/%s" % (os.path.dirname(cfg_path),
                            os.path.basename(cfg_path))
        if os.path.exists(tmp):
            cfg_path = tmp

        if (target_filename):
            target_path = os.path.join(self.astetcdir, target_filename)
        else:
            target_path = os.path.join(self.astetcdir,
                                       os.path.basename(cfg_path))

        if os.path.exists(target_path):
            os.remove(target_path)
        try:
            shutil.copyfile(cfg_path, target_path)
            self._file_replace_string(target_path);
        except shutil.Error:
            LOGGER.warn("'%s' and '%s' are the same file" %
                        (cfg_path, target_path))
        except IOError:
            LOGGER.warn("The destination is not writable '%s'" % target_path)

    def install_files(self, source_path):
        """Installs all files located in a directory to this
        instance of Asterisk.

        Keyword Arguments:
        source_path This argument must be the path to the directory
                 containing the files to be installed into standard
                 locations.

                 Example: tests/my-cool-test/files/ast1
                 This directory must contain at least one sub-directory
                 matching the name of an entry from the asterisk.conf
                 "directories" category.  For example "astvarlibdir".
                 Each entry in those directories will be copied to the
                 runtime equivalent for the test.

        Example:
            Given the following filesystem layout:
            tests/my-cool-test/files/ast1
                                    - astvarlibdir/
                                        - sounds/
                                            - recordings/
                                                - myrecording.ulaw
                                    - astkeydir/keys/
                                        - mykey.pem

            ...and given the following entries in asterisk.conf:
            astvarlibdir => /var/lib/asterisk
            astkeydir => /var/lib/asterisk

            The myrecording.ulaw and mykey.pem files would be copied to
            <testroot>/var/lib/asterisk/sounds/recordings/ and
            <testroot>/var/lib/asterisk/keys/ respectively.
        """

        self._make_directory_structure()
        if not os.path.exists(source_path):
            return

        for fname in os.listdir(source_path):
            source = "%s/%s" % (source_path, fname)

            if os.path.isdir(source):
                # If the directory name isn't one of the
                # well known directories, just skip it.
                if not self.directories[fname]:
                    continue
                # join() doesn't work if one of the paths is absolute
                # so we have to skip the leading '/' in the directory
                # entry.  I.E /var/lib/asterisk becomes var/lib/asterisk
                direntry = self.directories[fname]
                dirpath = direntry[1:] if direntry[0] == '/' else direntry
                dest = os.path.join(self.base, dirpath)
                polyfill.copytree(source, dest, dirs_exist_ok=True)

    def _overwrite_file(self, filename, values):
        """Overwrite a particular config file

        Keyword Arguments:
        filename The name of the conf file to overwrite
        values A list of key/value pair tuples to write to the file
        """
        target_filename = os.path.join(self.astetcdir, filename)

        if not os.path.exists(target_filename):
            LOGGER.error("File '%s' does not exists" % filename)
            return
        try:
            ofile = open(target_filename, "w")
        except IOError:
            LOGGER.error("Failed to open %s" % target_filename)
            return
        except:
            LOGGER.error("Unexpected error: %s" % sys.exc_info()[0])
            return

        for (var, val) in values:
            ofile.write('%s = %s\n' % (var, val))

        ofile.close()

    def cli_originate(self, argstr):
        """Starts a call from the CLI and links it to an application or
        context.

        Must pass a valid argument string in the following form:

        <tech/data> application <appname> appdata
        <tech/data> extension <exten>@<context>

        If no context is specified, the 'default' context will be
        used. If no extension is given, the 's' extension will be used.

        Keyword Arguments:
        argstr Arguments to be passed to the originate

        Returns:
        A deferred object that can be used to listen for command completion

        Example Usage:
        asterisk.originate("Local/a_exten@context extension b_exten@context")
        """

        args = argstr.split()
        raise_error = False
        if len(args) != 3 and len(args) != 4:
            raise_error = True
            LOGGER.error("Wrong number of arguments.")
        if args[1] != "extension" and args[1] != "application":
            raise_error = True
            LOGGER.error('2nd argument must be "extension" or "application"')
        if args[0].find("/") == -1:
            raise_error = True
            LOGGER.error('Channel dial string must be in the form "tech/data".')
        if raise_error is True:
            raise Exception(
                "Cannot originate call!\n"
                "Argument string must be in one of these forms:\n"
                "<tech/data> application <appname> appdata\n"
                "<tech/data> extension <exten>@<context>")

        return self.cli_exec("channel originate %s" % argstr)

    def cli_exec(self, cli_cmd):
        """Execute a CLI command on this instance of Asterisk.

        Keyword Arguments:
        cli_cmd The command to execute.

        Returns:
        A deferred object that will be signaled when the process has exited

        Example Usage:
        asterisk.cli_exec("core set verbose 10")
        """
        # If this is going to a remote system, make sure we enclose
        # the command in quotes
        if self.remote_config:
            cli_cmd = '"{0}"'.format(cli_cmd)

        cmd = [
            self.ast_binary,
            "-C", "%s" % os.path.join(self.astetcdir, "asterisk.conf"),
            "-rx", "%s" % cli_cmd
        ]
        LOGGER.debug("Executing %s ..." % cmd)
        if not self.remote_config:
            cli_protocol = AsteriskCliCommand(self.host, cmd)
        else:
            cli_protocol = AsteriskRemoteCliCommand(self.remote_config, cmd)
        return cli_protocol.execute()

    def _make_directory_structure(self):
        """ Mirror system directory structure """

        if self._directory_structure_made:
            return

        # Make the directory structure if not available
        if not os.path.exists(self.base):
            os.makedirs(self.base)

        dir_cat = None
        for cat in self._ast_conf.categories:
            if cat.name == "directories":
                dir_cat = cat
        if dir_cat is None:
            LOGGER.error("Unable to discover dir layout from asterisk.conf")
            raise Exception("Unable to discover dir layout from asterisk.conf")

        self._gen_ast_conf(dir_cat, self._ast_conf_options)

        # Cache mirrored dirs to speed up creation. Generally you'll have
        # /var/lib/asterisk for more than one dir_cat option, and that happens
        # to be the largest dir too (with lots of sounds).
        cache = set()
        for (var, val) in dir_cat.options:
            # We cannot simply skip ``val`` here if we already processed it.
            # Some dirs are exempt from copying, based on ``var``.
            if var != "astcachedir":
                self.__mirror_dir(var, val, cache)

        self._directory_structure_made = True

    def _setup_configs(self):
        """Perform any post-installation manipulation of the config files"""

        if self._configs_set_up:
            return
        self._setup_manager_conf()
        self._configs_set_up = True

    def _setup_manager_conf(self):
        """Forcibly create a manger.general.conf.inc file for non-localhosts"""

        if self.host == '127.0.0.1':
            return
        values = [('bindaddr', self.host), ]
        self._overwrite_file("manager.general.conf.inc", values)

    def _gen_ast_conf(self, dir_cat, ast_conf_options):
        """Generate a default asterisk.conf"""
        for (var, val) in dir_cat.options:
            if var == "astetcdir":
                self.astetcdir = "%s%s" % (self.base, val)
                os.makedirs(self.astetcdir)

        local_ast_conf_path = os.path.join(self.astetcdir, "asterisk.conf")

        try:
            ast_file = open(local_ast_conf_path, "w")
        except IOError:
            LOGGER.error("Failed to open %s" % local_ast_conf_path)
            return
        except:
            LOGGER.error("Unexpected error: %s" % sys.exc_info()[0])
            return

        for cat in self._ast_conf.categories:
            ast_file.write("[%s]\n" % cat.name)
            if cat.name == "directories":
                for (var, val) in cat.options:
                    ast_file.write("%s = %s%s\n" % (var, self.base, val))
            elif cat.name == "options":
                ast_file.write("#include \"%s/asterisk.options.conf.inc\"\n" %
                               (self.astetcdir))
                if ast_conf_options:
                    for (var, val) in ast_conf_options.items():
                        ast_file.write("%s = %s\n" % (var, val))
                for (var, val) in cat.options:
                    if not ast_conf_options or var not in ast_conf_options:
                        ast_file.write("%s = %s\n" % (var, val))
            else:
                for (var, val) in cat.options:
                    ast_file.write("%s = %s\n" % (var, val))
            ast_file.write("\n")

        ast_file.close()

    def _get_module_conflicts(self, deps):
        """Attempt to get modules this test conflicts with"""
        if not deps:
            return []

        conflicts = []
        conflict_file_name = os.getcwd() + '/configs/' + 'conflicts.txt'
        try:
            with open(conflict_file_name, 'r') as conflict_file:
                for line in conflict_file:
                    line = line.strip()
                    if not line or line[0] == ';':
                        continue

                    key, val = line.split('=')
                    if next((dep for dep in deps if dep.name in key), None):
                        for value in val.split(','):
                            conflicts.append(value.strip())
        except:
            pass
        return conflicts

    def _append_modules_conf(self, deps):
        """Prevent modules from loading based on dependency conflicts"""
        conflicts = self._get_module_conflicts(deps)

        if not conflicts:
            return

        modules_conf = os.path.join(self.astetcdir, "modules.conf")
        try:
            with open(modules_conf, "a") as modules_file:
                for conflict in conflicts:
                    modules_file.write('noload => %s\n' % conflict)
        except IOError:
            LOGGER.error("Failed to open %s" % modules_conf)
            return
        except:
            LOGGER.error("Unexpected error: %s" % sys.exc_info()[0])
            return

    def __mirror_dir(self, ast_dir_name, ast_dir_path, cache):
        """Mirror an Asterisk directory for a test run"""
        self._makedirs(ast_dir_path)
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

    def _makedirs(self, ast_dir_path):
        """Make the Asterisk directories"""
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

            for dirname in dirnames:
                self._makedirs(os.path.join(target_dir, short_dirname, dirname))


class CLIPluggableActionModule(object):
    """Pluggable CLI action module.

    Options:
        id - The Asterisk id to execute the command on. This is optional and,
             if not specified defaults to 0 (ast1).
        cmd - The CLI command to execute
    """

    def __init__(self, test_object, config):
        """Setup the CLI event observer"""

        self.test_object = test_object

        if not isinstance(config, list):
            config = [config]

        self.cmds = config

    def run(self, triggered_by, source, extra):
        """Callback called when this action is triggered."""

        for cmd in self.cmds:
            text = cmd.get('cmd')
            if text:
                instance = cmd.get('id', 0)
                self.test_object.ast[instance].cli_exec(text)


PLUGGABLE_ACTION_REGISTRY.register("cli-cmds", CLIPluggableActionModule)

# vim: set ts=8 sw=4 sts=4 et ai tw=79:
