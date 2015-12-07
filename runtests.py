#!/usr/bin/env python
'''Asterisk external test suite driver.

Copyright (C) 2015, Digium, Inc.
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
import shutil
import xml.dom
import random
import select
import signal
import syslog

try:
    import lxml.etree as ET
except:
    # Ensure ET is defined
    ET = None

# Re-open stdout so it's line buffered.
# This allows timely processing of piped output.
newfno = os.dup(sys.stdout.fileno())
os.close(sys.stdout.fileno())
sys.stdout = os.fdopen(newfno, 'w', 1)

# Ensure logs directory exists before importing
# anything that might use logging.
if not os.path.isdir("logs"):
    os.mkdir("logs")

sys.path.append("lib/python")

from asterisk.version import AsteriskVersion
from asterisk.asterisk import Asterisk
from asterisk.test_config import TestConfig
from mailer import send_email

TESTS_CONFIG = "tests.yaml"
TEST_RESULTS = "asterisk-test-suite-report.xml"

# If True, abandon the current running TestRun. Used by SIGTERM.
abandon_test = False

# If True, abandon the current running TestSuite. Used by SIGUSR1/SIGTERM.
abandon_test_suite = False

# Set to True if any refs logs are processed
ref_debug_is_enabled = False

class TestRun:
    def __init__(self, test_name, ast_version, options, global_config=None, timeout=-1):
        self.can_run = False
        self.did_run = False
        self.time = 0.0
        self.test_name = test_name
        self.ast_version = ast_version
        self.options = options
        self.test_config = TestConfig(test_name, global_config)
        self.failure_message = ""
        self.__check_can_run(ast_version)
        self.stdout = ""
        self.timeout = timeout
        self.cleanup = options.cleanup
        self.skipped_reason = ""

        assert self.test_name.startswith('tests/')
        self.test_relpath = self.test_name[6:]

    def stdout_print(self, msg):
        self.stdout += msg + "\n"
        print msg

    def run(self):
        self.passed = False
        self.did_run = True
        start_time = time.time()
        os.environ['TESTSUITE_ACTIVE_TEST'] = self.test_name
        cmd = [
            "%s/run-test" % self.test_name,
        ]

        if not os.path.exists(cmd[0]):
            cmd = ["./lib/python/asterisk/test_runner.py",
                   "%s" % self.test_name]
        if os.path.exists(cmd[0]) and os.access(cmd[0], os.X_OK):
            self.stdout_print("Running %s ..." % cmd)
            cmd.append(str(self.ast_version).rstrip())
            p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT)
            self.pid = p.pid

            poll = select.poll()
            poll.register(p.stdout, select.POLLIN)

            timedout = False
            try:
                while (not abandon_test):
                    try:
                        if not poll.poll(self.timeout):
                            timedout = True
                            p.terminate()
                    except select.error as v:
                        if v[0] != errno.EINTR:
                            raise
                    l = p.stdout.readline()
                    if not l:
                        break
                    self.stdout_print(l)
            except IOError:
                pass
            p.wait()

            # Sanitize p.returncode so it's always a boolean.
            did_pass = (p.returncode == 0 and not abandon_test)
            if did_pass and not self.test_config.expect_pass:
                self.stdout_print("Test passed but was expected to fail.")
            if not did_pass and not self.test_config.expect_pass:
                print "Test failed as expected."

            self.passed = (did_pass == self.test_config.expect_pass)
            if abandon_test:
                self.passed = False

            core_dumps = self._check_for_core()
            if (len(core_dumps)):
                if self.passed:
                    self.stdout_print("Core dumps detected; failing test")
                    self.passed = False
                else:
                    self.stdout_print("Core dumps detected; test was already failed")
                self._archive_core_dumps(core_dumps)

            self._process_valgrind()
            self._process_ref_debug()

            if not self.passed:
                self._archive_logs()
            elif self.cleanup:
                try:
                    (run_num, run_dir, archive_dir) = self._find_run_dirs()
                    symlink_dir = os.path.dirname(run_dir)
                    absolute_dir = os.path.join(os.path.dirname(symlink_dir),
                                                os.readlink(symlink_dir))
                    shutil.rmtree(absolute_dir)
                    os.remove(symlink_dir)
                except:
                    print "Unable to clean up directory for" \
                          "test %s (non-fatal)" % self.test_name

            self.__parse_run_output(self.stdout)
            if timedout:
                status = 'timed out'
            elif abandon_test:
                status = 'was abandoned'
            elif self.passed:
                status = 'passed'
            else:
                status = 'failed'
            pass_str = 'Test %s %s\n' % (cmd, status)
            print pass_str
            if self.options.syslog:
                syslog.syslog(pass_str)

        else:
            print "FAILED TO EXECUTE %s, it must exist and be executable" % cmd
        self.time = time.time() - start_time

    def _check_for_core(self):
        core_files = []

        contents = os.listdir('.')
        for item in contents:
            if item.startswith('core') or item.startswith('vgcore'):
                core_files.append(item)

        contents = os.listdir(self.test_name)
        for item in contents:
            if item.startswith('core') or item.startswith('vgcore'):
                core_files.append(os.path.join(self.test_name, item))

        return core_files

    def _email_crash_report(self, dest_file_name):
        email_config = load_yaml_config("crash-mail-config.yaml")

        smtp_server = email_config.get('smtp-server')
        sender = email_config.get('sender')
        recipients = email_config.get('recipients')
        subject = email_config.get('subject', "Testsuite crash detected")
        max_bt_len = email_config.get('truncate-backtrace', 0)
        debug_level = email_config.get('debug', 0)

        if not sender or len(recipients) == 0:
            print "--email-on-crash requires sender and 1+ recipients"
            return

        with open(dest_file_name, 'r') as bt_file:
            backtrace_text = bt_file.read()

        if max_bt_len > 0 and backtrace_text > max_bt_len:
            truncated_text = "\n--truncated to {0} chars--".format(max_bt_len)
            backtrace_text = backtrace_text[0:max_bt_len] + truncated_text

        email_text = "{0}\n\n{1}".format(dest_file_name, backtrace_text)

        message = {'body': email_text, 'subject': subject}

        try:
            send_email(smtp_server, sender, recipients, message,
                       debug=debug_level)
        except Exception as exception:
            print "Failed to send email\nError: {0}".format(exception)

    def _archive_core_dumps(self, core_dumps):
        for core in core_dumps:
            if not os.path.exists(core):
                print "Unable to find core dump file %s, skipping" % core
                continue
            random_num = random.randint(0, 16000)
            dest_dir = "./logs/%s" % self.test_relpath
            if not os.path.exists(dest_dir):
                os.makedirs(dest_dir)
            dest_file_name = os.path.join(dest_dir,
                                          "backtrace_{0}.txt".format(random_num))
            dest_file = open(dest_file_name, "w")
            gdb_cmd = ["gdb",
                       "-se", "asterisk",
                       "-ex", "bt full",
                       "-ex", "thread apply all bt",
                       "--batch",
                       "-c", core]
            print "Running %s" % (" ".join(gdb_cmd),)
            try:
                res = subprocess.call(gdb_cmd, stdout=dest_file, stderr=subprocess.STDOUT)
                if res != 0:
                    print "error analyzing core dump; gdb exited with %d" % res
                # Copy the backtrace over to the logs
                print "Archived backtrace: {0}".format(dest_file_name)

                if self.options.email_on_crash:
                    self._email_crash_report(dest_file_name)

            except OSError, ose:
                print "OSError ([%d]: %s) occurred while executing %r" % \
                    (ose.errno, ose.strerror, gdb_cmd)
            except:
                print "Unknown exception occurred while executing %r" % (gdb_cmd,)
            finally:
                dest_file.close()
                if self.options.keep_core:
                    try:
                        dst_core = os.path.join(dest_dir, "core_{0}".format(random_num))
                        shutil.copy(core, dst_core)
                        print "Archived core file: {0}".format(dst_core)
                    except Exception as e:
                        print "Error occurred while copying core: {0}".format(e)
                try:
                    os.unlink(core)
                except OSError, e:
                    print "Error removing core file: %s: " \
                          "Beware of the stale core file in CWD!" % (e,)

    def _find_run_dirs(self):
        test_run_dir = os.path.join(Asterisk.test_suite_root,
                                    self.test_relpath)

        i = 1
        # Find the last run
        while os.path.isdir(os.path.join(test_run_dir, 'run_%d' % i)):
            i += 1
        run_num = i - 1
        run_dir = os.path.join(test_run_dir, 'run_%d' % run_num)
        archive_dir = os.path.join('./logs',
                                   self.test_relpath,
                                   'run_%d' % run_num)
        return (run_num, run_dir, archive_dir)

    def _process_valgrind(self):
        (run_num, run_dir, archive_dir) = self._find_run_dirs()
        if (run_num == 0):
            return
        if not ET:
            return

        i = 1
        while os.path.isdir(os.path.join(run_dir, 'ast%d/var/log/asterisk' % i)):
            ast_dir = "%s/ast%d/var/log/asterisk" % (run_dir, i)
            valgrind_xml = os.path.join(ast_dir, 'valgrind.xml')
            valgrind_txt = os.path.join(ast_dir, 'valgrind-summary.txt')

            # All instances either use valgrind or not.
            if not os.path.exists(valgrind_xml):
                return

            dom = ET.parse(valgrind_xml)
            xslt = ET.parse('contrib/valgrind/summary-lines.xsl')
            transform = ET.XSLT(xslt)
            newdom = transform(dom)
            lines = []
            for node in newdom.getroot():
                if node.tag == 'line':
                    lines.append((node.text or '').strip())
                elif node.tag == 'cols':
                    lines.append("%s: %s" % (
                        node.attrib['col1'].strip().rjust(20),
                        node.attrib['col2'].strip()))

            self.stdout_print("\n".join(lines))
            with open(valgrind_txt, 'a') as txtfile:
                txtfile.write("\n".join(lines))
                txtfile.close()
            i += 1

    def _process_ref_debug(self):
        (run_num, run_dir, archive_dir) = self._find_run_dirs()
        if (run_num == 0):
            return

        refcounter_py = os.path.join(run_dir,
                                     "ast1/var/lib/asterisk/scripts/refcounter.py")
        if not os.path.exists(refcounter_py):
            return

        i = 1
        while os.path.isdir(os.path.join(run_dir, 'ast%d/var/log/asterisk' % i)):
            ast_dir = "%s/ast%d/var/log/asterisk" % (run_dir, i)
            refs_in = os.path.join(ast_dir, "refs")
            if os.path.exists(refs_in):
                global ref_debug_is_enabled
                ref_debug_is_enabled = True

                refs_txt = os.path.join(ast_dir, "refs.txt")
                dest_file = open(refs_txt, "w")
                refcounter = [
                    refcounter_py,
                    "-f", refs_in,
                    "-sn"
                ]
                res = -1
                try:
                    res = subprocess.call(refcounter,
                                          stdout=dest_file,
                                          stderr=subprocess.STDOUT)
                except Exception, e:
                    self.stdout_print("Exception occurred while processing REF_DEBUG")
                finally:
                    dest_file.close()
                if res != 0:
                    dest_dir = os.path.join(archive_dir,
                                            'ast%d/var/log/asterisk' % i)
                    if not os.path.exists(dest_dir):
                        os.makedirs(dest_dir)
                    hardlink_or_copy(refs_txt,
                                     os.path.join(dest_dir, "refs.txt"))
                    hardlink_or_copy(refs_in,
                                     os.path.join(dest_dir, "refs"))
                    if self.passed:
                        self.stdout_print("REF_DEBUG identified leaks, "
                                          "mark test as failure")
                        self.passed = False
                    else:
                        self.stdout_print("REF_DEBUG identified leaks, "
                                          "test was already marked as failure")
            i += 1

    def _archive_files(self, src_dir, dest_dir, *filenames):
        for filename in filenames:
            try:
                srcfile = os.path.join(src_dir, filename)
                if os.path.exists(srcfile):
                    hardlink_or_copy(srcfile, os.path.join(dest_dir, filename))
            except Exception, e:
                print "Exception occurred while archiving file '%s' to %s: %s" % (
                    srcfile, dest_dir, e
                )

    def _archive_logs(self):
        (run_num, run_dir, archive_dir) = self._find_run_dirs()
        self._archive_ast_logs(run_num, run_dir, archive_dir)
        self._archive_pcap_dump(run_dir, archive_dir)
        self._archive_files(run_dir, archive_dir, 'messages.txt', 'full.txt')

    def _archive_ast_logs(self, run_num, run_dir, archive_dir):
        """Archive the Asterisk logs"""
        i = 1
        while os.path.isdir(os.path.join(run_dir, 'ast%d/var/log/asterisk' % i)):
            ast_dir = "%s/ast%d/var/log/asterisk" % (run_dir, i)
            dest_dir = os.path.join(archive_dir,
                                    'ast%d/var/log/asterisk' % i)
            self._archive_files(ast_dir, dest_dir,
                                'messages.txt', 'full.txt', 'mmlog',
                                'valgrind.xml', 'valgrind-summary.txt')
            i += 1

    def _archive_pcap_dump(self, run_dir, archive_dir):
        self._archive_files(run_dir, archive_dir, 'dumpfile.pcap')

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
        self.start_time = None
        self.global_config = self._parse_global_config()
        self.tests = self._parse_test_yaml("tests", ast_version)
        if self.options.randomorder:
            random.shuffle(self.tests)
        else:
            self.tests = sorted(self.tests, key=lambda test: test.test_name)
        self.total_time = 0.0
        self.total_count = 0
        self.total_failures = 0
        self.total_skipped = 0

    def _parse_global_config(self):
        return TestConfig(os.getcwd())

    def _parse_test_yaml(self, test_dir, ast_version):
        tests = []

        config = load_yaml_config("%s/%s" % (test_dir, TESTS_CONFIG))
        if not config:
            return tests

        for t in config["tests"]:
            for val in t:
                path = "%s/%s" % (test_dir, t[val])
                if val == "test":
                    # If we specified a subset of tests, there's no point loading
                    # the others.
                    if (self.options.tests and
                            not any((path + '/').startswith(test)
                                    for test in self.options.tests)):
                        continue

                    tests.append(TestRun(path, ast_version, self.options,
                                         self.global_config, self.options.timeout))
                elif val == "dir":
                    tests += self._parse_test_yaml(path, ast_version)

        return tests

    def list_tags(self):
        def chunks(l, n):
            for i in xrange(0, len(l), n):
                yield l[i:(i + n)]

        tags = set()
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
            if t.test_config.skip is not None:
                print "      --> Skip: %s" % t.test_config.skip
            print ("      --> Minimum Version: %s (%s)" %
                   (", ".join([str(v) for v in t.test_config.minversion]),
                    t.test_config.minversion_check))
            if t.test_config.maxversion is not None:
                print ("      --> Maximum Version: %s (%s)" %
                       (", ".join([str(v) for v in t.test_config.maxversion]),
                        t.test_config.maxversion_check))
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
                    print "        --> Version: %s -- Met: %s" % (d.version, str(d.met))
                else:
                    print "      --> Dependency: %s -- Met: %s" % (d.name, str(d.met))

            i += 1

    def run(self):
        self.start_time = time.strftime("%Y-%m-%dT%H:%M:%S %Z", time.localtime())
        test_suite_dir = os.getcwd()
        i = 0
        for t in self.tests:
            if t.can_run is False:
                continue
            if self.global_config is not None:
                for excluded in self.global_config.excluded_tests:
                    if excluded in t.test_name:
                        continue
            i += 1
        print "Tests to run: %d,  Maximum test inactivity time: %d sec." % \
            (i, (self.options.timeout / 1000))

        for t in self.tests:
            if abandon_test_suite:
                break

            if t.can_run is False:
                if t.test_config.skip is not None:
                    print "--> %s ... skipped '%s'" % (t.test_name, t.test_config.skip)
                    t.skipped_reason = t.test_config.skip
                    self.total_skipped += 1
                    continue
                print "--> Cannot run test '%s'" % t.test_name
                if t.test_config.forced_version is not None:
                    print "--- --> Forced Asterisk Version: %s" % \
                        (str(t.test_config.forced_version))
                print ("--- --> Minimum Version: %s (%s)" %
                       (", ".join([str(v) for v in t.test_config.minversion]),
                        t.test_config.minversion_check))
                if t.test_config.maxversion is not None:
                    print ("--- --> Maximum Version: %s (%s)" %
                           (", ".join([str(v) for v in t.test_config.maxversion]),
                            t.test_config.maxversion_check))
                for f in t.test_config.features:
                    print "--- --> Version Feature: %s - %s" % (
                        f, str(t.test_config.feature_check[f]))
                print "--- --> Tags: %s" % (t.test_config.tags)
                for d in t.test_config.deps:
                    print "--- --> Dependency: %s - %s" % (d.name, str(d.met))
                print
                self.total_skipped += 1
                t.skipped_reason = "Failed dependency"
                continue
            if self.global_config is not None:
                exclude = False
                for excluded in self.global_config.excluded_tests:
                    if excluded in t.test_name:
                        print "--- ---> Excluded test: %s" % excluded
                        exclude = True
                if exclude:
                    self.total_skipped += 1
                    continue

            running_str = "--> Running test '%s' ..." % t.test_name
            print running_str
            if self.options.syslog:
                syslog.syslog(running_str)

            if self.options.dry_run:
                t.passed = True
            else:
                # Establish Preconditions
                print "Making sure Asterisk isn't running ..."
                if os.system("if pidof asterisk >/dev/null; then "
                             "killall -9 asterisk >/dev/null 2>&1; "
                             "sleep 1; ! pidof asterisk >/dev/null; fi"):
                    print "Could not kill asterisk."
                print "Making sure SIPp isn't running..."
                if os.system("if pidof sipp >/dev/null; then "
                             "killall -9 sipp >/dev/null 2>&1; "
                             "sleep 1; ! pidof sipp >/dev/null; fi"):
                    print "Could not kill sipp."
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
            for i in range(r[0], r[1] + 1):
                char_list.append(chr(i))
        return data.translate(None, ''.join(char_list))

    def write_results_xml(self, doc, root):

        ts = doc.createElement("testsuite")
        root.appendChild(ts)
        ts.setAttribute("errors", "0")
        ts.setAttribute("tests", str(self.total_count))
        ts.setAttribute("time", "%.2f" % self.total_time)
        ts.setAttribute("failures", str(self.total_failures))
        ts.setAttribute("name", "AsteriskTestSuite")
        ts.setAttribute("timestamp", self.start_time)
        if self.options.dry_run:
            ts.setAttribute("skipped", str(self.total_count))
        elif self.total_skipped > 0:
            ts.setAttribute("skipped", str(self.total_skipped))

        for t in self.tests:
            tc = doc.createElement("testcase")
            ts.appendChild(tc)
            tc.setAttribute("time", "%.2f" % t.time)
            tc.setAttribute("name", t.test_name)

            if t.did_run is False:
                tskip = doc.createElement("skipped")
                tskip.appendChild(doc.createTextNode(str(t.skipped_reason)))
                tc.appendChild(tskip)
                continue

            if t.passed:
                continue

            failure = doc.createElement("failure")
            failure.appendChild(doc.createTextNode(
                self.__strip_illegal_xml_chars(t.failure_message)))
            tc.appendChild(failure)

    def generate_refleaks_summary(self):
        dest_file = open("./logs/refleaks-summary.txt", "w")
        try:
            subprocess.call("./contrib/scripts/refleaks-summary",
                                  stdout=dest_file,
                                  stderr=subprocess.STDOUT)
        finally:
            dest_file.close()



def load_yaml_config(path):
    """Load contents of a YAML config file to a dictionary"""
    try:
        f = open(path, "r")
    except IOError:
        # Ignore errors for the optional tests/custom folder.
        if path != "tests/custom/tests.yaml":
            print "Failed to open %s" % path
        return None
    except:
        print "Unexpected error: %s" % sys.exc_info()[0]
        return None

    config = yaml.load(f)
    f.close()

    return config


def handle_usr1(sig, stack):
    """Handle the SIGUSR1 signal

    This should instruct the running test suite to exit as soon as possible
    """
    global abandon_test_suite

    print "SIGUSR1 received; stopping test suite after current test..."
    abandon_test_suite = True


def handle_term(sig, stack):
    """Handle the SIGTERM signal

    This should abandon the current running test, marking it as failed, and
    gracefully exit the current running test suite as soon as possible
    """
    global abandon_test
    global abandon_test_suite

    print "SIGTREM received; abandoning current test and stopping..."
    abandon_test = True
    abandon_test_suite = True


def main(argv=None):
    if argv is None:
        args = sys.argv

    usage = "Usage: ./runtests.py [options]"

    parser = optparse.OptionParser(usage=usage)
    parser.add_option("-c", "--cleanup", action="store_true",
                      dest="cleanup", default=False,
                      help="Cleanup tmp directory after each successful test")
    parser.add_option("-d", "--dry-run", action="store_true",
                      dest="dry_run", default=False,
                      help="Only show which tests would be run.")
    parser.add_option("-g", "--tag", action="append",
                      dest="tags",
                      help="Specify one or more tags to select a subset of tests.")
    parser.add_option("-k", "--keep-core", action="store_true",
                      dest="keep_core", default=False,
                      help="Archive the 'core' file if Asterisk crashes.")
    parser.add_option("-l", "--list-tests", action="store_true",
                      dest="list_tests", default=False,
                      help="List tests instead of running them.")
    parser.add_option("-L", "--list-tags", action="store_true",
                      dest="list_tags", default=False,
                      help="List available tags")
    parser.add_option("-s", "--syslog", action="store_true",
                      dest="syslog", default=False,
                      help="Log test start/stop to syslog")
    parser.add_option("-t", "--test", action="append", default=[],
                      dest="tests",
                      help="Run a single specified test (directory) instead "
                           "of all tests.  May be specified more than once.")
    parser.add_option("-v", "--version",
                      dest="version", default=None,
                      help="Specify the version of Asterisk rather then detecting it.")
    parser.add_option("-V", "--valgrind", action="store_true",
                      dest="valgrind", default=False,
                      help="Run Asterisk under Valgrind")
    parser.add_option("--email-on-crash", action="store_true",
                      dest="email_on_crash", default=False,
                      help="Send email on crash with a backtrace. See "
                           "crash-mail-config.yaml.sample for details.")
    parser.add_option("--number", metavar="int", type=int,
                      dest="number", default=1,
                      help="Number of times to run the test suite. If a value of "
                           "-1 is provided, the test suite will loop forever.")
    parser.add_option("--random-order", action="store_true",
                      dest="randomorder", default=False,
                      help="Shuffle the tests so they are run in random order")
    parser.add_option("--timeout", metavar='int', type=int,
                      dest="timeout", default=-1,
                      help="Abort test after n seconds of no output.")
    (options, args) = parser.parse_args(argv)

    # Install a signal handler for USR1/TERM, and use it to bail out of running
    # any remaining tests
    signal.signal(signal.SIGUSR1, handle_usr1)
    signal.signal(signal.SIGTERM, handle_term)

    ast_version = AsteriskVersion(options.version)

    if options.list_tests or options.list_tags:
        test_suite = TestSuite(ast_version, options)

        print "Asterisk Version: %s\n" % str(ast_version)

        if options.list_tests:
            test_suite.list_tests()

        if options.list_tags:
            test_suite.list_tags()

        return 0

    if options.timeout > 0:
        options.timeout *= 1000

    # Ensure that there's a trailing '/' in the tests specified with -t
    for i, test in enumerate(options.tests):
        if not test.endswith('/'):
            options.tests[i] = test + '/'

    if options.valgrind:
        if not ET:
            print "python lxml module not loaded, text summaries " \
                  "from valgrind will not be produced.\n"
        os.environ["VALGRIND_ENABLE"] = "true"

    dom = xml.dom.getDOMImplementation()
    doc = dom.createDocument(None, "testsuites", None)

    continue_forever = True if options.number < 0 else False
    iteration = 0
    if options.syslog:
        syslog.openlog('AsteriskTestsuite', syslog.LOG_PID)
    while ((iteration < options.number or continue_forever) and not abandon_test_suite):

        test_suite = TestSuite(ast_version, options)

        running_str = "Running tests for Asterisk {0} (run {1})...\n".format(
            str(ast_version).strip('\n'), iteration + 1)
        print running_str
        if options.syslog:
            syslog.syslog(running_str)

        test_suite.run()
        test_suite.write_results_xml(doc, doc.documentElement)

        # If exactly one test was requested, then skip the summary.
        if len(test_suite.tests) != 1:
            print "\n=== TEST RESULTS ===\n"
            print "PATH: %s\n" % os.getenv("PATH")
            for t in test_suite.tests:
                sys.stdout.write("--> %s --- " % t.test_name)
                if t.did_run is False:
                    print "SKIPPED"
                    for d in t.test_config.deps:
                        print "      --> Dependency: %s -- Met: %s" % (d.name, str(d.met))
                    if options.tags:
                        for t in t.test_config.tags:
                            print "      --> Tag: %s -- Met: %s" % (t, str(t in options.tags))
                    continue
                if t.passed is True:
                    print "PASSED"
                else:
                    print "FAILED"

        iteration += 1

    if ref_debug_is_enabled:
        test_suite.generate_refleaks_summary()

    try:
        with open(TEST_RESULTS, "w") as f:
            doc.writexml(f, addindent="  ", newl="\n", encoding="utf-8")
    except IOError:
        print "Failed to open test results output file: %s" % TEST_RESULTS
    except:
        print "Unexpected error: %s" % sys.exc_info()[0]
    print "\n"
    print doc.toprettyxml("  ", encoding="utf-8")

    if options.syslog:
        syslog.syslog("All tests concluded")
        syslog.closelog()

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
