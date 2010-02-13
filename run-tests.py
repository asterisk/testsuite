#!/usr/bin/env python
'''
Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import os
import subprocess
import optparse
import yaml


TESTS_CONFIG = "tests/tests.yaml"


class Dependency:
    def __init__(self, name):
        self.name = name
        self.found = self.__which(name) is not None

    def __which(self, program):
        '''
        http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
        '''
        def is_exe(fpath):
            return os.path.exists(fpath) and os.access(fpath, os.X_OK)

        fpath, fname = os.path.split(program)
        if fpath:
            if is_exe(program):
                return program
        else:
            for path in os.environ["PATH"].split(os.pathsep):
                exe_file = os.path.join(path, program)
                if is_exe(exe_file):
                    return exe_file

        return None


class TestConfig:
    def __init__(self, test_name):
        test_config = "tests/%s/test-config.yaml" % test_name
        try:
            f = open(test_config, "r")
            self.config = yaml.load(f)
            f.close()
        except:
            print "Failed to open %s, does it exist?" % test_config

        self.test_name = test_name
        try:
            self.summary = self.config["testinfo"]["summary"]
        except:
            self.summary = ""
        try:
            self.description = self.config["testinfo"]["description"]
        except:
            self.description = ""

        self.deps = [
            Dependency(d["depend"])
                for d in self.config["properties"]["dependencies"]
        ]

        self.can_run = True
        for d in self.deps:
            if d.found is False:
                self.can_run = False
                break


class TestsConfig:
    def __init__(self):
        f = open(TESTS_CONFIG, "r")
        self.config = yaml.load(f)
        f.close()

        self.tests = [ TestConfig(t["test"]) for t in self.config["tests"] ]

    def __str__(self):
        s = "Configured tests:\n"
        i = 1
        for t in self.tests:
            s += "%.3d) %s (%s)\n" % (i, t.test_name, t.summary)
            i += 1
        return s


def main(argv=None):
    if argv is None:
        args = sys.argv

    parser = optparse.OptionParser()
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    (options, args) = parser.parse_args(argv)

    tests_config = TestsConfig()

    if options.list_tests is True:
        print tests_config
        sys.exit(0)

    print "Running tests ...\n"

    for t in tests_config.tests:
        if t.can_run is False:
            print "--> Can not run test '%s'" % t.test_name
            for d in t.deps:
                print "--- --> Dependency: %s - %s" % (d.name, str(d.found))
            print
            continue

        print "--> Can run test '%s'\n" % t.test_name

        p = subprocess.Popen(
            ["tests/%s/run-test" % t.test_name, "-v", "ASTVERSIONGOESHERE"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT
        )

        t.stdout = ""
        for line in p.stdout:
            print line
            t.stdout += line
        p.wait()
        t.passed = p.returncode == 0

    print "=== TEST RESULTS ==="
    for t in tests_config.tests:
        sys.stdout.write("--> %s --- " % t.test_name)
        if t.passed is True:
            print "PASSED"
        else:
            print "FAILED"


if __name__ == "__main__":
    main()
