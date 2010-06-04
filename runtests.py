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
        self.did_run = False
        self.time = 0.0
        self.test_name = test_name
        self.ast_version = ast_version

        self.__parse_config()
        self.__check_deps(ast_version)

    def run(self):
        self.passed = False
        self.did_run = True
        start_time = time.time()
        cmd = [
            "tests/%s/run-test" % self.test_name,
            "-v", str(self.ast_version)
        ]
        if os.path.exists(cmd[0]) and os.access(cmd[0], os.X_OK):
            print "Running %s ..." % cmd
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
            p2 = subprocess.Popen(["tee", "tests/%s/test-output.txt" %
                                   self.test_name], stdin=p.stdout)
            p.wait()
            p2.wait()
            self.passed = p.returncode == 0
        else:
            print "FAILED TO EXECUTE %s, it must exist and be executable" % cmd
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
                print "ERROR: '%s' is not a valid minversion" % \
                        properties["minversion"]
        if "maxversion" in properties:
            try:
                self.maxversion = AsteriskVersion(properties["maxversion"])
            except:
                self.can_run = False
                print "ERROR: '%s' is not a valid maxversion" % \
                        properties["maxversion"]

    def __parse_config(self):
        test_config = "tests/%s/test-config.yaml" % self.test_name
        try:
            f = open(test_config, "r")
        except IOError:
            print "Failed to open %s" % test_config
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        self.config = yaml.load(f)
        f.close()

        self.__process_testinfo()
        self.__process_properties()

    def __check_deps(self, ast_version):
        self.deps = [
            Dependency(d)
                for d in self.config["properties"].get("dependencies") or []
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
    def __init__(self, ast_version, options):
        try:
            f = open(TESTS_CONFIG, "r")
        except IOError:
            print "Failed to open %s" % TESTS_CONFIG
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        self.options = options

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
            print "%.3d) %s" % (i, t.test_name)
            print "      --> Summary: %s" % t.summary
            print "      --> Minimum Version: %s (%s)" % \
                         (str(t.minversion), str(t.minversion_check))
            if t.maxversion is not None:
                print "      --> Maximum Version: %s (%s)" % \
                             (str(t.maxversion), str(t.maxversion_check))
            for d in t.deps:
                print "      --> Dependency: %s -- Met: %s" % (d.name,
                             str(d.met))
            i += 1

    def run(self):
        test_suite_dir = os.getcwd()

        for t in self.tests:
            if self.options.test and t.test_name != self.options.test:
                continue
            if t.can_run is False:
                print "--> Cannot run test '%s'" % t.test_name
                print "--- --> Minimum Version: %s (%s)" % \
                    (str(t.minversion), str(t.minversion_check))
                if t.maxversion is not None:
                    print "--- --> Maximum Version: %s (%s)" % \
                        (str(t.maxversion), str(t.maxversion_check))
                for d in t.deps:
                    print "--- --> Dependency: %s - %s" % (d.name, str(d.met))
                print
                continue

            print "--> Running test '%s' ...\n" % t.test_name

            # Establish Preconditions
            print "Making sure Asterisk isn't running ..."
            os.system("killall -9 asterisk > /dev/null 2>&1")
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
            print "Failed to open test results output file: %s" % TEST_RESULTS
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<testsuite errors="0" time="%.2f" tests="%d" '
                'name="AsteriskTestSuite">\n' %
                (self.total_time, len(self.tests)))
        for t in self.tests:
            if t.did_run is False:
                continue
            f.write('\t<testcase time="%.2f" name="%s"' % (t.time, t.test_name))
            if t.passed is True:
                f.write('/>\n')
                continue
            f.write(">\n\t\t<failure><![CDATA[\n")
            try:
                test_output = open("tests/%s/test-output.txt" % t.test_name, "r")
                f.write("%s" % test_output.read())
                test_output.close()
            except IOError:
                print "Failed to open test output for %s" % t.test_name
            f.write("\n\t\t]]></failure>\n\t</testcase>\n")
        f.write('</testsuite>\n')
        f.close()

        if stdout is True:
            try:
                f = open(TEST_RESULTS, "r")
            except IOError:
                print "Failed to open test results output file: %s" % \
                        TEST_RESULTS
            except:
                print "Unexpected error: %s" % sys.exc_info()[0]
            else:
                print f.read()
                f.close()


def main(argv=None):
    if argv is None:
        args = sys.argv

    usage = "Usage: ./runtests.py [options]\n\n" + BIG_WARNING

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    parser.add_option("-t", "--test",
            dest="test",
            help="Run a single specified test instead of all tests.")
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

    test_suite = TestSuite(ast_version, options)

    if options.list_tests is True:
        print "Asterisk Version: %s\n" % str(ast_version)
        test_suite.list_tests()
        return 0

    if os.geteuid() != 0:
        print "You must run this script as root."
        print BIG_WARNING
        return 1

    print "Running tests for Asterisk %s ...\n" % str(ast_version)

    test_suite.run()

    print "\n=== TEST RESULTS ==="
    for t in test_suite.tests:
        sys.stdout.write("--> %s --- " % t.test_name)
        if t.did_run is False:
            print "SKIPPED"
            continue
        if t.passed is True:
            print "PASSED"
        else:
            print "FAILED"

    print "\n"

    test_suite.write_results_xml(TEST_RESULTS, stdout=True)


if __name__ == "__main__":
    sys.exit(main() or 0)
