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

sys.path.append("lib/python")

from asterisk.version import AsteriskVersion


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
    def __init__(self, dep):
        self.name = ""
        self.met = False
        if "app" in dep:
            self.name = dep["app"]
            self.met = self.__which(self.name) is not None
        elif "python" in dep:
            self.name = dep["python"]
            try:
                __import__(self.name)
                self.met = True
            except ImportError:
                pass
        else:
            print "Unknown dependency type specified."

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
        self.ast_version = ast_version

        self.__parse_config()
        self.__check_deps(ast_version)

    def run(self):
        self.passed = False
        start_time = time.time()
        cmd = [
            "tests/{0}/run-test".format(self.test_name),
            "-v", str(self.ast_version)
        ]
        if os.path.exists(cmd[0]):
            print "Running {0} ...".format(cmd)
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["tee", "tests/{0}/test-output.txt".format(
                                   self.test_name)], stdin=p.stdout)
            p.wait()
            p2.wait()
            self.passed = p.returncode == 0
        self.time = time.time() - start_time

    def __process_testinfo(self):
        self.summary = "(none)"
        self.description = "(none)"
        if "testinfo" not in self.config:
            return
        testinfo = self.config["testinfo"]
        if "summary" in testinfo:
            self.summary = testinfo["summary"]
        if "description" in testinfo:
            self.description = testinfo["description"]

    def __process_properties(self):
        self.minversion = AsteriskVersion("1.4")
        self.maxversion = None
        if "properties" not in self.config:
            return
        properties = self.config["properties"]
        if "minversion" in properties:
            try:
                self.minversion = AsteriskVersion(properties["minversion"])
            except:
                self.can_run = False
                print "ERROR: '{0}' is not a valid minversion".format(
                        properties["minversion"])
        if "maxversion" in properties:
            try:
                self.maxversion = AsteriskVersion(properties["maxversion"])
            except:
                self.can_run = False
                print "ERROR: '{0}' is not a valid maxversion".format(
                        properties["maxversion"])

    def __parse_config(self):
        test_config = "tests/{0}/test-config.yaml".format(self.test_name)
        try:
            f = open(test_config, "r")
        except IOError:
            print "Failed to open {0}".format(test_config)
            return
        except:
            print "Unexpected error: {0}".format(sys.exc_info()[0])
            return

        self.config = yaml.load(f)
        f.close()

        self.__process_testinfo()
        self.__process_properties()

    def __check_deps(self, ast_version):
        self.deps = [
            Dependency(d)
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
            if d.met is False:
                self.can_run = False
                break


class TestSuite:
    def __init__(self, ast_version):
        try:
            f = open(TESTS_CONFIG, "r")
        except IOError:
            print "Failed to open {0}".format(TESTS_CONFIG)
            return
        except:
            print "Unexpected error: {0}".format(sys.exc_info()[0])
            return

        self.config = yaml.load(f)
        f.close()

        self.total_time = 0.0

        self.tests = [
            TestConfig(t["test"], ast_version) for t in self.config["tests"]
        ]

    def list_tests(self):
        print "Configured tests:"
        i = 1
        for t in self.tests:
            print "{0:3d}) {1}".format(i, t.test_name)
            print "      --> Summary: {0}".format(t.summary)
            print "      --> Minimum Version: {0} ({1})".format(
                         t.minversion, t.minversion_check)
            if t.maxversion is not None:
                print "      --> Maximum Version: {0} ({1})".format(
                             t.maxversion, t.maxversion_check)
            for d in t.deps:
                print "      --> Dependency: {0} -- Met: {1}".format(d.name,
                             d.met)
            i += 1

    def run(self, ast_version):
        test_suite_dir = os.getcwd()

        for t in self.tests:
            if t.can_run is False:
                print "--> Can not run test '{0}'".format(t.test_name)
                for d in t.deps:
                    print "--- --> Dependency: {0} - {1}".format(d.name, d.met)
                print
                continue

            print "--> Running test '{0}' ...\n".format(t.test_name)

            # Establish Preconditions
            os.chdir("..")
            print "Uninstalling Asterisk ... "
            os.system("make uninstall-all > /dev/null 2>&1")
            print "Installing Asterisk ... "
            os.system("make install > /dev/null 2>&1")
            print "Installing sample configuration ... "
            os.system("make samples > /dev/null 2>&1")
            os.chdir(test_suite_dir)

            # Run Test

            t.run()
            self.total_time += t.time

    def write_results_xml(self, fn, stdout=False):
        try:
            f = open(TEST_RESULTS, "w")
        except IOError:
            print "Failed to open file: {0}".format(TEST_RESULTS)
            return
        except:
            print "Unexpected error: {0}".format(sys.exc_info()[0])
            return

        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<testsuite errors="0" time="{0:.2f}" tests="{1}" '
                'name="AsteriskTestSuite">\n'.format(
                self.total_time, len(self.tests)))
        for t in self.tests:
            if t.can_run is False:
                continue
            f.write('\t<testcase time="{0:.2f}" name="{1}"'.format(t.time, t.test_name))
            if t.passed is True:
                f.write('/>\n')
                continue
            f.write(">\n\t\t<failure><![CDATA[\n")
            try:
                test_output = open("tests/{0}/test-output.txt".format(
                                                            t.test_name), "r")
                f.write(test_output.read())
                test_output.close()
            except IOError:
                print "Failed to open test output for {0}".format(t.test_name)
            f.write("\n\t\t]]></failure>\n\t</testcase>\n")
        f.write('</testsuite>\n')
        f.close()

        if stdout is True:
            try:
                f = open(TEST_RESULTS, "r")
            except IOError:
                print "Failed to open test results output file: {0}".format(
                        TEST_RESULTS)
            except:
                print "Unexpected error: {0}".format(sys.exc_info()[0])
            else:
                print f.read()
                f.close()


def main(argv=None):
    if argv is None:
        args = sys.argv

    usage = "Usage: ./runtests.py [options]\n" \
            "\n" \
            "{0}".format(BIG_WARNING)

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    (options, args) = parser.parse_args(argv)

    # Check to see if this has been executed within a sub directory of an
    # Asterisk source tree.  This is required so that we can execute
    # install and uninstall targets of the Asterisk Makefile in between
    # tests.
    if os.path.exists("../main/asterisk.c") is False:
        print "***  ERROR  ***\n" \
              "runtests has not been executed from within a\n" \
              "subdirectory of an Asterisk source tree.  This\n" \
              "is required for being able to uninstall and install\n" \
              "Asterisk in between tests.\n" \
              "***************\n"
        return 1

    ast_version = AsteriskVersion()

    test_suite = TestSuite(ast_version)

    if options.list_tests is True:
        print "Asterisk Version: {0}\n".format(ast_version)
        test_suite.list_tests()
        return 0

    if os.geteuid() != 0:
        print "You must run this script as root."
        print BIG_WARNING
        return 1

    print "Running tests for Asterisk {0} ...\n".format(ast_version)

    test_suite.run(ast_version)

    print "\n=== TEST RESULTS ==="
    for t in test_suite.tests:
        if t.can_run is False:
            continue
        sys.stdout.write("--> {0} --- ".format(t.test_name))
        if t.passed is True:
            print "PASSED"
        else:
            print "FAILED"

    print "\n"

    test_suite.write_results_xml(TEST_RESULTS, stdout=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
