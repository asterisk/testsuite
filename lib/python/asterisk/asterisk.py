#!/usr/bin/env python
""" Asterisk Instances in Python.

This module provides an interface for creating instances of Asterisk
from within python code.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import sys
import os
import signal
import time
import shutil
import subprocess

from config import ConfigFile

from version import AsteriskVersion


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
    """

    def __init__(self, base=None):
        """Construct an Asterisk instance.

        Keyword Arguments:
        base -- This is the root of the files associated with this instance of
        Asterisk.  By default, the base is "tmp/" within the current working
        directory.  Given a base, a unique directory name will be generated to
        hold all files.

        Example Usage:
        self.asterisk = Asterisk(base=os.path.join(os.getcwd(),
                                                   "tests/ami-login/tmp"))
        """
        self.ast_version = AsteriskVersion()

        self.astetcdir = "/etc/asterisk"
        # Find the system installed asterisk.conf
        ast_confs = [
                "/etc/asterisk/asterisk.conf",
                "/usr/local/etc/asterisk/asterisk.conf"
        ]
        ast_conf = None
        for c in ast_confs:
            if os.path.exists(c):
                ast_conf = ConfigFile(c)
                break
        if ast_conf is None:
            print "No asterisk.conf found on the system!"
            return

        # Choose an install base
        self.base = base
        if self.base is None:
            self.base = "%s/tmp" % os.getcwd()
        i = 1
        while True:
            if not os.path.isdir("%s/ast%d" % (self.base, i)):
                self.base = "%s/ast%d" % (self.base, i)
                break
            i += 1
        os.makedirs(self.base)

        # Mirror system install directory structure
        dir_cat = None
        for c in ast_conf.categories:
            if c.name == "directories":
                dir_cat = c
        if dir_cat is None:
            print "Unable to discover dir layout from asterisk.conf"
            return
        self.__gen_ast_conf(ast_conf, dir_cat)
        for (var, val) in dir_cat.options:
            self.__mirror_dir(var, val)

    def start(self):
        """Start this instance of Asterisk.

        This function starts up this instance of Asterisk.

        Example Usage:
        asterisk.start()
        """
        cmd = [
            "asterisk",
            "-f", "-g", "-q", "-m",
            "-C", "%s" % os.path.join(self.astetcdir, "asterisk.conf")
        ]
        self.process = subprocess.Popen(cmd)
        # Be _really_ sure that Asterisk has started up before returning.
        time.sleep(5.0)
        self.cli_exec("core waitfullybooted")

    def stop(self):
        """Stop this instance of Asterisk.

        This function is used to stop this instance of Asterisk.

        Example Usage:
        asterisk.stop()
        """
        if self.ast_version < AsteriskVersion("1.6.0"):
            self.cli_exec("stop gracefully")
        else:
            self.cli_exec("core stop gracefully")
        try:
            os.kill(self.process.pid, signal.SIGTERM)
            time.sleep(5.0)
            if not self.process.poll():
                os.kill(self.process.pid, signal.SIGKILL)
        except OSError:
            pass
        self.process.wait()
        return self.process.returncode

    def install_config(self, cfg_path):
        """Install a custom configuration file for this instance of Asterisk.

        By default, the configuration used will be whatever is found in the
        system install of Asterisk.  However, custom configuration files to be
        used only by this instance can be provided via this API call.

        Keyword Arguments:
        cfg_path -- This argument must be the path to the configuration file
        to be installed into the directory tree for this instance of Asterisk.

        Example Usage:
        asterisk.install_config("tests/my-cool-test/configs/manager.conf")
        """
        if not os.path.exists(cfg_path):
            print "Config file '%s' does not exist" % cfg_path
            return
        target_path = os.path.join(self.astetcdir, os.path.basename(cfg_path))
        if os.path.exists(target_path):
            os.remove(target_path)
        try:
            shutil.copyfile(cfg_path, target_path)
        except shutil.Error:
            print "'%s' and '%s' are the same file" % (cfg_path, target_path)
        except IOError:
            print "The destination is not writable '%s'" % target_path

    def cli_exec(self, cli_cmd):
        """Execute a CLI command on this instance of Asterisk.

        Keyword Arguments:
        cli_cmd -- The command to execute.

        Example Usage:
        asterisk.cli_exec("core set verbose 10")
        """
        cmd = 'asterisk -C %s -rx "%s"' % \
                (os.path.join(self.astetcdir, "asterisk.conf"), cli_cmd)
        print "Executing %s ..." % cmd
        process = subprocess.Popen(cmd, shell=True)
        process.wait()

    def __gen_ast_conf(self, ast_conf, dir_cat):
        for (var, val) in dir_cat.options:
            if var == "astetcdir":
                self.astetcdir = "%s%s" % (self.base, val)
                os.makedirs(self.astetcdir)

        local_ast_conf_path = os.path.join(self.astetcdir, "asterisk.conf")

        try:
            f = open(local_ast_conf_path, "w")
        except IOError:
            print "Failed to open %s" % local_ast_conf_path
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        for c in ast_conf.categories:
            f.write("[%s]\n\n" % c.name)
            if c.name == "directories":
                for (var, val) in c.options:
                    f.write("%s = %s%s\n" % (var, self.base, val))
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
        blacklist = [ "astdb" ]
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

