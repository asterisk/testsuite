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
import time
import yaml

from asteriskversion import AsteriskVersion


TESTS_CONFIG = "tests/tests.yaml"
TEST_RESULTS = "asterisk-test-suite-report.xml"

BIG_WARNING = "\n" \
              "      *** PLEASE NOTE ***\n" \
              "Running this script will completely wipe out any remnants of\n" \
              "an existing Asterisk installation.  Please ensure you only run\n"\
              "this in a test environment.\n" \
              "\n" \
              "EXISTING CONFIGURATION WILL BE LOST!\n" \
              "      *******************\n"


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
    def __init__(self, test_name, ast_version):
        self.can_run = True
        self.time = 0.0
        self.test_name = test_name

        self.__parse_config()
        self.__check_deps(ast_version)

    def __process_testinfo(self):
        self.summary = "(none)"
        self.description = "(none)"
        if self.config.has_key("testinfo") is False:
            return
        testinfo = self.config["testinfo"]
        if testinfo.has_key("summary"):
            self.summary = testinfo["summary"]
        if testinfo.has_key("description"):
            self.description = testinfo["description"]

    def __process_properties(self):
        self.minversion = AsteriskVersion("1.4")
        self.maxversion = None
        if self.config.has_key("properties") is False:
            return
        properties = self.config["properties"]
        if properties.has_key("minversion"):
            self.minversion = AsteriskVersion(properties["minversion"])
        if properties.has_key("maxversion"):
            self.maxversion = AsteriskVersion(properties["maxversion"])

    def __parse_config(self):
        test_config = "tests/%s/test-config.yaml" % self.test_name
        try:
            f = open(test_config, "r")
            self.config = yaml.load(f)
            f.close()
        except:
            print "Failed to open %s, does it exist?" % test_config

        self.__process_testinfo()
        self.__process_properties()

    def __check_deps(self, ast_version):
        self.deps = [
            Dependency(d["app"])
                for d in self.config["properties"]["dependencies"]
        ]

        self.minversion_check = True
        if ast_version < self.minversion:
            self.can_run = False
            self.minversion_check = False
            return

        self.maxversion_check = True
        if self.maxversion is not None and ast_version > self.maxversion:
            self.can_run = False
            self.maxversion_check = False
            return

        for d in self.deps:
            if d.found is False:
                self.can_run = False
                break


class TestSuite:
    def __init__(self, ast_version):
        f = open(TESTS_CONFIG, "r")
        self.config = yaml.load(f)
        f.close()

        self.total_time = 0.0

        # Check to see if this has been executed within a sub directory of an
        # Asterisk source tree.  This is required so that we can execute
        # install and uninstall targets of the Asterisk Makefile in between
        # tests.
        self.within_ast_tree = os.path.exists("../main/asterisk.c")
        if self.within_ast_tree is False:
            print "*** WARNING ***\n" \
                  "run-tests has not been executed from within a\n" \
                  "subdirectory of an Asterisk source tree.  This\n" \
                  "is required for being able to uninstall and install\n" \
                  "Asterisk in between tests.\n" \
                  "***************\n"

        self.tests = [
            TestConfig(t["test"], ast_version) for t in self.config["tests"]
        ]

    def __str__(self):
        s = "Configured tests:\n"
        i = 1
        for t in self.tests:
            s += "%.3d) %s\n" % (i, t.test_name)
            s += "      --> Summary: %s\n" % t.summary
            s += "      --> Minimum Version: %s (%s)\n" % \
                            (str(t.minversion), str(t.minversion_check))
            if t.maxversion is not None:
                s += "      --> Maximum Version: %s (%s) \n" % \
                            (str(t.maxversion), str(t.maxversion_check))
            i += 1
        return s

    def run(self, ast_version):
        test_suite_dir = os.getcwd()

        for t in self.tests:
            if t.can_run is False:
                print "--> Can not run test '%s'" % t.test_name
                for d in t.deps:
                    print "--- --> Dependency: %s - %s" % (d.name, str(d.found))
                print
                continue

            print "--> Running test '%s' ...\n" % t.test_name

            # Establish Preconditions

            if self.within_ast_tree is True:
                os.chdir("..")
                os.system("make uninstall-all")
                os.system("make install")
                os.system("make samples")
                os.chdir(test_suite_dir)

            # Run Test

            cmd = ["tests/%s/run-test" % t.test_name]
            cmd.extend(["-v", str(ast_version)])

            start_time = time.time()
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            t.time = time.time() - start_time
            self.total_time += t.time

            t.stdout = ""
            for line in p.stdout:
                print line
                t.stdout += line
            p.wait()
            t.passed = p.returncode == 0

    def write_results_xml(self, fn, stdout=False):
        try:
            f = open(TEST_RESULTS, "w")
        except:
            print "Failed to open test results output file."
            return

        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<testsuite errors="0" time="%.2f" tests="%d" '
                'name="AsteriskTestSuite">\n' %
                (self.total_time, len(self.tests)))
        for t in self.tests:
            if t.can_run is False:
                continue
            f.write('\t<testcase time="%.2f" name="%s"' % (t.time, t.test_name))
            if t.passed is True:
                f.write('/>\n')
                continue
            f.write('>\t\t<failure>%s</failure>\n\t</testcase>' % t.stdout)
        f.write('</testsuite>\n')
        f.close()

        if stdout is True:
            f = open(TEST_RESULTS, "r")
            print f.read()
            f.close()


def main(argv=None):
    if argv is None:
        args = sys.argv

    usage = "Usage: ./run-tests.py [options]\n" \
            "\n" \
            "%s" % BIG_WARNING

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    (options, args) = parser.parse_args(argv)

    ast_version = AsteriskVersion()

    test_suite = TestSuite(ast_version)

    if options.list_tests is True:
        print "Asterisk Version: %s\n" % str(ast_version)
        print test_suite
        sys.exit(0)

    if os.geteuid() != 0:
        print "You must run this script as root."
        print BIG_WARNING
        sys.exit(1)

    print "Running tests for Asterisk %s ...\n" % str(ast_version)

    test_suite.run(ast_version)

    print "\n=== TEST RESULTS ==="
    for t in test_suite.tests:
        if t.can_run is False:
            continue
        sys.stdout.write("--> %s --- " % t.test_name)
        if t.passed is True:
            print "PASSED"
        else:
            print "FAILED"

    print "\n"

    test_suite.write_results_xml(TEST_RESULTS, stdout=True)


if __name__ == "__main__":
    main()
