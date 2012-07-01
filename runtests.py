#!/usr/bin/env python
'''Asterisk external test suite driver.

Copyright (C) 2010, Digium, Inc.
Russell Bryant <russell@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
'''

import sys
import os
import errno
import subprocess
import optparse
import time
import yaml
import socket
import shutil
import xml.dom
import random

sys.path.append("lib/python")

from asterisk.version import AsteriskVersion
from asterisk.asterisk import Asterisk
from asterisk.TestConfig import Dependency, TestConfig
from asterisk import TestSuiteUtils

TESTS_CONFIG = "tests.yaml"
TEST_RESULTS = "asterisk-test-suite-report.xml"

class TestRun:
    def __init__(self, test_name, ast_version, options):
        self.can_run = False
        self.did_run = False
        self.time = 0.0
        self.test_name = test_name
        self.ast_version = ast_version
        self.options = options
        self.test_config = TestConfig(test_name)
        self.failure_message = ""
        self.__check_can_run(ast_version)
        self.stdout = ""

    def run(self):
        self.passed = False
        self.did_run = True
        start_time = time.time()
        cmd = [
            "%s/run-test" % self.test_name,
        ]

        if not os.path.exists(cmd[0]):
            cmd = ["./lib/python/asterisk/TestRunner.py",
                   "%s" % self.test_name]
        if os.path.exists(cmd[0]) and os.access(cmd[0], os.X_OK):
            msg = "Running %s ..." % cmd
            print msg
            self.stdout += msg + "\n"
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            self.pid = p.pid
            try:
                for l in p.stdout.readlines():
                    print l,
                    self.stdout += l
            except IOError:
                pass
            p.wait()

            self.__parse_run_output(self.stdout)

            self.passed = (p.returncode == 0 and self.test_config.expectPass) or (p.returncode and not self.test_config.expectPass)
            core_dumps = self.__check_for_core()
            if (len(core_dumps)):
                print "Core dumps detected; failing test"
                self.passed = False
                self.__archive_core_dumps(core_dumps)
            if not self.passed:
                self.__archive_ast_logs()
                self.__archive_pcap_dump()

        else:
            print "FAILED TO EXECUTE %s, it must exist and be executable" % cmd
        self.time = time.time() - start_time

    def __check_for_core(self):
        contents = os.listdir('.')
        core_files = []
        for item in contents:
            if item.startswith('core.'):
                core_files.append(item)
        return core_files

    def __archive_core_dumps(self, core_dumps):
        for core in core_dumps:
            if not os.path.exists(core):
                print "Unable to find core dump file %s, skipping" % core
                continue
            random_num = random.randint(0, 16000)
            dest_dir = "./logs/%s" % self.test_name.lstrip("tests/")
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            dest_file = open(dest_dir + "/backtrace_%s.txt" % str(random_num), "w")
            gdb_cmd = ["gdb", "-se", "asterisk", "-ex", "bt full", "-ex", "thread apply all bt", "--batch", "-c", core]
            print "Running %s" % (" ".join(gdb_cmd),)
            try:
                res = subprocess.call(gdb_cmd, stdout=dest_file, stderr=subprocess.STDOUT)
                if res != 0:
                    print "error analyzing core dump; gdb exited with %d" % res
                """ Copy the backtrace over to the logs """
            except OSError, ose:
                print "OSError ([%d]: %s) occurred while executing %r" % (ose.errno, ose.strerror, gdb_cmd)
                return
            except:
                print "Unknown exception occurred while executing %r" % (gdb_cmd,)
                return
            finally:
                dest_file.close()
                try:
                    os.rename(core, "%s/core_%s" % (dest_dir,str(random_num)))
                except OSError, e:
                    print "Error moving core file: %s: Beware of the stale core file in CWD!" % (e,)

    def __archive_ast_logs(self):
        ast_directories = "%s/%s" % (Asterisk.test_suite_root, self.test_name.lstrip("tests/"))
        i = 1
        while True:
            if os.path.isdir("%s/ast%d" % (ast_directories, i)):
                ast_dir = "%s/ast%d/var/log/asterisk" % (ast_directories, i)
                dest_dir = "./logs/%s/ast%d/var/log/asterisk" % (self.test_name.lstrip("tests/"), i)
                """ Only archive the logs if we havent archived it for this test run yet """
                if not os.path.exists(dest_dir):
                    try:
                        hardlink_or_copy(ast_dir + "/messages.txt", dest_dir + "/messages.txt")
                        hardlink_or_copy(ast_dir + "/full.txt", dest_dir + "/full.txt")
                    except Exception, e:
                        print "Exception occurred while archiving logs from %s to %s: %s" % (
                            ast_dir, dest_dir, e
                        )
            else:
                break
            i += 1

    def __archive_pcap_dump(self):
        filename = "dumpfile.pcap"
        test_base = self.test_name.lstrip("tests/")
        src = os.path.join(Asterisk.test_suite_root, test_base, str(self.pid), filename)
        dst = os.path.join("logs", test_base, filename)
        if os.path.exists(src):
            try:
                hardlink_or_copy(src, dst)
            except Exception, e:
                print "Exeception occured while archiving pcap file from %s to %s: %s" % (
                    src, dst, e
                )

    def __check_can_run(self, ast_version):
        """Check tags and dependencies in the test config."""
        if self.test_config.check_deps(ast_version) and \
                self.test_config.check_tags(self.options.tags):
            self.can_run = True

    def __parse_run_output(self, output):
        self.failure_message = output


class TestSuite:
    def __init__(self, ast_version, options):
        self.options = options

        self.tests = []
        self.tests = self._parse_test_yaml("tests", ast_version)
        self.global_config = self._parse_global_config()
        self.total_time = 0.0
        self.total_count = 0
        self.total_failures = 0

    def _parse_global_config(self):
        return TestConfig(os.getcwd())

    def _parse_test_yaml(self, test_dir, ast_version):
        tests = []
        try:
            f = open("%s/%s" % (test_dir, TESTS_CONFIG), "r")
        except IOError:
            print "Failed to open %s" % TESTS_CONFIG
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        config = yaml.load(f)
        f.close()

        for t in config["tests"]:
            for val in t:
                path = "%s/%s" % (test_dir, t[val])
                if val == "test":
                    # If we specified a subset of tests, there's no point loading the others.
                    if self.options.test and not (path + '/').startswith(self.options.test):
                        continue

                    tests.append(TestRun(path, ast_version, self.options))
                elif val == "dir":
                    tests += self._parse_test_yaml(path, ast_version)

        return tests

    def list_tags(self):
        def chunks(l, n):
            for i in xrange(0, len(l), n):
                yield l[i:i+n]

        tags= set()
        for test in self.tests:
            tags = tags.union(test.test_config.tags)
        tags = list(set(tags))
        tags.sort(key=str.lower)
        maxwidth = max(len(t) for t in tags)

        print "Available test tags:"
        tags = chunks(tags, 3)
        for tag in tags:
            print "\t%-*s     %-*s     %-*s" % (
                maxwidth, tag[0],
                maxwidth, len(tag) > 1 and tag[1] or '',
                maxwidth, len(tag) > 2 and tag[2] or '')

    def list_tests(self):
        print "Configured tests:"
        i = 1
        for t in self.tests:
            print "%.3d) %s" % (i, t.test_config.test_name)
            print "      --> Summary: %s" % t.test_config.summary
            print "      --> Minimum Version: %s (%s)" % \
                         (str(t.test_config.minversion), str(t.test_config.minversion_check))
            if t.test_config.maxversion is not None:
                print "      --> Maximum Version: %s (%s)" % \
                             (str(t.test_config.maxversion), str(t.test_config.maxversion_check))
            if t.test_config.features:
                print "      --> Features:"
                for feature_name in t.test_config.features:
                    print "        --> %s: -- Met: %s" % \
                        (feature_name, str(t.test_config.feature_check[feature_name]))
            if t.test_config.tags:
                print "      --> Tags: %s" % str(t.test_config.tags)
            for d in t.test_config.deps:
                if d.version:
                    print "      --> Dependency: %s" % (d.name)
                    print "        --> Version: %s -- Met: %s" % (d.version,
                            str(d.met))
                else:
                    print "      --> Dependency: %s -- Met: %s" % (d.name,
                             str(d.met))

            i += 1

    def run(self):
        test_suite_dir = os.getcwd()

        for t in self.tests:
            if t.can_run is False:
                if t.test_config.skip is not None:
                    print "--> %s ... skipped '%s'" % (t.test_name, t.test_config.skip)
                    continue
                print "--> Cannot run test '%s'" % t.test_name
                print "--- --> Minimum Version: %s (%s)" % \
                    (str(t.test_config.minversion), str(t.test_config.minversion_check))
                if t.test_config.maxversion is not None:
                    print "--- --> Maximum Version: %s (%s)" % \
                        (str(t.test_config.maxversion), str(t.test_config.maxversion_check))
                for f in t.test_config.features:
                    print "--- --> Version Feature: %s - %s" % (f, str(t.test_config.feature_check[f]))
                print "--- --> Tags: %s" % (t.test_config.tags)
                for d in t.test_config.deps:
                    print "--- --> Dependency: %s - %s" % (d.name, str(d.met))
                print
                continue
            if self.global_config != None:
                exclude = False
                for excluded in self.global_config.excludedTests:
                    if excluded in t.test_name:
                        print "--- ---> Excluded test: %s" % excluded
                        exclude = True
                if exclude:
                    continue

            print "--> Running test '%s' ...\n" % t.test_name

            # Establish Preconditions
            print "Making sure Asterisk isn't running ..."
            os.system("killall -9 asterisk > /dev/null 2>&1")
            # XXX TODO Hard coded path, gross.
            os.system("rm -f /var/run/asterisk/asterisk.ctl")
            os.system("rm -f /var/run/asterisk/asterisk.pid")
            os.chdir(test_suite_dir)

            # Run Test

            t.run()
            self.total_count += 1
            self.total_time += t.time
            if t.passed is False:
                self.total_failures += 1

    def __strip_illegal_xml_chars(self, data):
        """
        Strip illegal XML characters from the given data. The character range
        is taken from section 2.2 of the XML spec.
        """
        bad_chars = [
            (0x0, 0x8),
            (0xb, 0xc),
            (0xe, 0x1f),
            (0x7f, 0x84),
            (0x86, 0x9f),
        ]

        char_list = []
        for r in bad_chars:
            # we do +1 here to include the last item
            for i in range(r[0], r[1]+1):
                char_list.append(chr(i))
        return data.translate(None, ''.join(char_list))

    def write_results_xml(self, fn, stdout=False):
        testOutput = ""
        try:
            f = open(TEST_RESULTS, "w")
        except IOError:
            print "Failed to open test results output file: %s" % TEST_RESULTS
            return
        except:
            print "Unexpected error: %s" % sys.exc_info()[0]
            return

        dom = xml.dom.getDOMImplementation()
        doc = dom.createDocument(None, "testsuite", None)

        ts = doc.documentElement
        ts.setAttribute("errors", "0")
        ts.setAttribute("tests", str(self.total_count))
        ts.setAttribute("time", "%.2f" % self.total_time)
        ts.setAttribute("failures", str(self.total_failures))
        ts.setAttribute("name", "AsteriskTestSuite")

        for t in self.tests:
            if t.did_run is False:
                continue

            tc = doc.createElement("testcase")
            ts.appendChild(tc)
            tc.setAttribute("time", "%.2f" % t.time)
            tc.setAttribute("name", t.test_name)

            if t.passed:
                continue

            failure = doc.createElement("failure")
            failure.appendChild(doc.createTextNode(self.__strip_illegal_xml_chars(t.failure_message)))
            tc.appendChild(failure)

        doc.writexml(f, addindent="  ", newl="\n", encoding="utf-8")
        f.close()

        if stdout:
            print doc.toprettyxml("  ", encoding="utf-8")


def main(argv=None):
    if argv is None:
        args = sys.argv

    usage = "Usage: ./runtests.py [options]"

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-l", "--list-tests", action="store_true",
            dest="list_tests", default=False,
            help="List tests instead of running them.")
    parser.add_option("-t", "--test",
            dest="test",
            help="Run a single specified test instead of all tests.")
    parser.add_option("-g", "--tag", action="append",
            dest="tags",
            help="Specify one or more tags to select a subset of tests.")
    parser.add_option("-v", "--version",
            dest="version", default=None,
            help="Specify the version of Asterisk rather then detecting it.")
    parser.add_option("-L", "--list-tags", action="store_true",
            dest="list_tags", default=False,
            help="List available tags")
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

    ast_version = AsteriskVersion(options.version)

    # Ensure that there's a trailing '/' in the test specified with -t
    if options.test and options.test[-1] != '/':
        options.test += '/'

    test_suite = TestSuite(ast_version, options)

    if options.list_tests:
        print "Asterisk Version: %s\n" % str(ast_version)
        test_suite.list_tests()
        return 0

    if options.list_tags:
        test_suite.list_tags()
        return 0

    print "Running tests for Asterisk %s ...\n" % str(ast_version)

    test_suite.run()

    test_suite.write_results_xml(TEST_RESULTS, stdout=True)

    if not options.test:
        print "\n=== TEST RESULTS ===\n"
        print "PATH: %s\n" % os.getenv("PATH")
        for t in test_suite.tests:
            sys.stdout.write("--> %s --- " % t.test_name)
            if t.did_run is False:
                print "SKIPPED"
                for d in t.test_config.deps:
                    print "      --> Dependency: %s -- Met: %s" % (d.name,
                                 str(d.met))
                if options.tags:
                    for t in t.test_config.tags:
                        print "      --> Tag: %s -- Met: %s" % (t, str(t in options.tags))
                continue
            if t.passed is True:
                print "PASSED"
            else:
                print "FAILED"

    print "\n"
    return test_suite.total_failures


def hardlink_or_copy(source, destination):
    """May raise all sorts of exceptions, most notably the OSError and
    the IOError."""
    if os.path.exists(destination):
        os.unlink(destination)
    else:
        destination_dir = os.path.dirname(destination)
        if not os.path.exists(destination_dir):
            os.makedirs(destination_dir)

    try:
        os.link(source, destination)
    except OSError, e:
        # Different partitions can cause hard links to fail (error 18),
        # if there's a different error, bail out immediately.
        if e.args[0] != errno.EXDEV:
            raise e

        # Try a copy instead
        shutil.copyfile(source, destination)


if __name__ == "__main__":
    sys.exit(main() or 0)
