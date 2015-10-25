================================================================================
===                                                                          ===
===                           Asterisk Test Suite                            ===
===                                                                          ===
===                         http://www.asterisk.org/                         ===
===                  Copyright (C) 2010 - 2015, Digium, Inc.                 ===
===                                                                          ===
================================================================================

--------------------------------------------------------------------------------
--- 0) Table of Contents
--------------------------------------------------------------------------------

    Using the Test Suite:
        1) Introduction
        2) Test Suite System Requirements
        3) Running the Test Suite
        4) External control of the Test Suite

    Writing Tests:
        5) Test Anatomy
        6) Test Configuration
        7) Tests in Python
        8) Tests in Lua
        9) Custom Tests

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 1) Introduction
--------------------------------------------------------------------------------

Over the years as the Asterisk code base has expanded, the need for more tools
to control the quality of the code has increased. Luckily some of these tools
have been implemented and the return on that investment has paid dividends
immediately.

There are four parts to code testing:

  1) Testing with our eyes

  2) Bottom-Up testing using unit tests within Asterisk

  3) Top-Down testing using an external test suite

  4) Tests running constantly using a continuous integration framework


With the introduction of ReviewBoard (http://reviewboard.asterisk.org) code is
now peer reviewed to a greater extent prior to being merged and the number of
pre-commit bugs being found is tremendous. ReviewBoard satisfies the first
part: Testing with our eyes.

But where peer reviewing fails is in the ability to verify that regressions are
not being introduced into the code. Whenever you solve a complex issue, the
chances that a regression is introduced somewhere else is elevated. A way of
minimizing those regressions is through automated testing.

Automated testing improves the quality of code at any part of the development
cycle and reduces the number of regressions being introduced. Whenever a part
of the system is being worked on and bugs are being resolved, developers are
encouraged to write tests in order to verify that the same issue does not creep
back into the code, and that changes in other locations do not disrupt the
expected results in that area.

The next two directions satisfy the bottom-up testing and top-down testing
methods:

Automated testing for Asterisk is approached from two directions.  The first is
bottom-up unit testing.  Those tests are implemented within Asterisk in the C
programming language, using the Asterisk C APIs.  These tests are enabled by
turning on the TEST_FRAMEWORK compile time option in menuselect.  The CLI
commands related to the test framework all begin with "test".

The second approach is top down using tests developed outside of Asterisk.
This test suite is the collection of top-down functionality tests. The test
suite is made up as a collection of scripts that test some portion of Asterisk
functionality given a set of preconditions, and then provide a pass/fail result
via a predefined method of doing so.

The fourth part ties parts two and three together by making sure that whenever
something is introduced that breaks one of the tests, that it gets resolved
immediately and not at some point in the future through bug reporting. This is
done with Bamboo. You can see the history and current status of the tests
being run by visiting http://bamboo.asterisk.org.

This document will focus on how you can setup the Asterisk Test Suite in order
to run the same automated external tests on your own development system. You
are also encouraged to write your own automated tests to verify parts of your
own system remain in working order, and to contribute those tests back to the
Asterisk project so they may be run in the automated testing framework.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 2) Test Suite System Requirements
--------------------------------------------------------------------------------

Required:
        - python >= 2.6.5
        - python-yaml
        - git-core

Note: Many commands below will install files into system directories;
if you are executing these commands as an unprivileged user, you might
need to use 'sudo' or similar.

Optional (needed by specific tests):
        - bash
        - SIPp
            - Download the latest unstable release
            - http://sipp.sourceforge.net/snapshots/
            - Compile the version with pcap and OpenSSL support using:
                  $ make pcapplay_ossl
            - Install sipp into a directory in the execution path:
                  $ cp sipp /usr/local/bin
        - asttest
            - include with the test suite
            - Install from the asttest directory
                  $ cd asttest
                  $ make
                  $ make install
        - Python modules
            - starpy
                - Install starpy from the addons directory
                  $ cd addons
                  $ make update
                  $ make install
            - python-twisted
            - python-lxml
        - pjsua
            - Download and build pjproject 1.x from source
            - http://www.pjsip.org/download.htm
            - On an x86-32 machine, run the configure script as follows:
              $ ./configure
            - On an x86-64 machine, run the configure script as follows:
              $ ./configure CFLAGS=-fPIC
            - There are tests in the testsuite that require IPv6
	      support in pjsua, so create a pjlib/include/pj/config_site.h
              file and add the line

              #define PJ_HAS_IPV6 1
            - Build
              $ make dep && make
            - On an x86-32 machine, copy the
              'pjsua-x86-unknown-linux-gnu' executable found in the
              pjsip-apps/bin/ directory to a directory located in the
              execution path, and name it 'pjsua'.
              $ cp pjsip-apps/bin/pjsua-x86-unknown-linux-gnu /usr/local/bin/pjsua
            - On an x86-64 machine, copy the
              'pjsua-x86_64-unknown-linux-gnu' executable found in the
              pjsip-apps/bin/ directory to a directory located in the
              execution path, and name it 'pjsua'.
              $ cp pjsip-apps/bin/pjsua-x86_64-unknown-linux-gnu /usr/local/bin/pjsua
        - pjsua python bindings
            - Go to pjsip-apps/src/python directory
            - Run 'sudo python ./setup.py install' or just 'sudo make install'
        - libpcap and yappcap
            - Install the libpcap development library package for your system
              (libpcap-dev for Debian-based distros, pcap-devel for Red Hat)
	    - Install cython
            - Download yappcap from:
              https://github.com/otherwiseguy/yappcap/tarball/master
            - tar -xvzf otherwiseguy-yappcap*.tar.gz
            - cd otherwiseguy-yappcap*
            - make && sudo make install
	    - Note that if you install these packages, you'll need to
              execute tests in the testsuite using an account with
              privileges to do raw packet captures ('root', of course,
              but other accounts may work on your system).

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 3) Running the Test Suite
--------------------------------------------------------------------------------

Get the Asterisk source tree you want to test:
    $ svn co http://svn.digium.com/svn/asterisk/trunk asterisk-trunk
    $ cd asterisk-trunk

Build and install it.
    $ ./configure && make
    $ make install

Check out the test suite:
    $ git clone http://gerrit.asterisk.org/testsuite
    $ cd testsuite

List the tests:
    $ ./runtests.py -l

       ******************************************
       *** Listing the tests will also tell   ***
       *** you which dependencies are missing ***
       ******************************************

Run the tests:
    $ ./runtests.py

Run multiple iterations:
    $ ./runtests.py --number 5

Run a specific test:
    $ ./runtests.py -t tests/pbx/dialplan

For more syntax information:
    $ ./runtests.py --help

As an alternative to the above, you can use run-local:

Get the Asterisk source tree you want to test:
    $ svn co http://svn.digium.com/svn/asterisk/trunk asterisk-trunk
    $ cd asterisk-trunk

Optionally configure and make it:
    $ ./configure && make

Check out the test suite:
    $ git clone http://gerrit.asterisk.org/testsuite
    $ cd testsuite

Setup the test environment:
    $ ./run-local setup

Run tests:
    $ ./run-local run # Add here any of runtests.py's parameters.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 4) External control of the Test Suite
--------------------------------------------------------------------------------

The Test Suite can be controlled externally using the SIGUSR1 and SIGTERM
signals.
    - SIGUSR1 will instruct the Test Suite to stop running any further tests
      after the current running test completes. Any tests not executed will be
      marked as skipped.
    - SIGTERM will attempt to immediately stop execution of the current test,
      marking it as failed. The Test Suite will stop running any further tests,
      marking any test not executed as skipped.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 5) Test Anatomy
--------------------------------------------------------------------------------

a) File layout

        Adding a test to the test suite is very easy to do.  Every test lives
within its own directory within the tests directory.  Within that directory,
there must be an executable called "run-test".  The test directory may contain
anything else that the test needs to do its job.  A test configuration file may
also exist that includes parameters that will be read by the top level test
script.

        /tests
          /mynewtest
             -> run-test
             -> test-config.yaml
             ...
        /configs
          -> asterisk.options.conf.inc
          -> logger.conf
          -> logger.general.conf.inc
          ...

        To have a test included in the test suite, it must be added to the
"tests.yaml" file that lives in the tests directory.  This configuration file
determines the order that the tests are considered for execution by the top
level test suite application.

        The purpose of the 'configs' directory is to define global settings for
Asterisk.  Tests will inherit these settings every time the testsuite creates
sandbox instances of Asterisk.  Additionally, tests have the ability to override
these setting, however it is NOT recommended they do so.  If you wanted to add a
setting to logger.conf [logfiles], you could create a 'logger.logfiles.conf.inc'
file for your test and the global Asterisk logger.conf will automatically
include it. The filename convention is <asterisk module>.<category>.conf.inc.
Again, settings in 'asterisk.options.conf.inc' would be included in
asterisk.conf [options] category.

b) Preconditions

        When the "run-test" application is executed, it can assume that the
system has a fresh install of Asterisk with files installed into their default
locations.  This includes a fresh set of sample configuration files in the
/etc/asterisk directory.

        For increased portability the shebang (#!) for "run-test" MUST begin
with "#!/usr/bin/env".  For exmaple: a test written in Python would have
"#!/usr/bin/env python" for the shebang.

c) Test configuration files

        All configuration files will now be stored in the 'configs/ast%d'
directory, depending on how many Asterisk instances your test uses, you create
additional 'ast%d' sub folders.  If you only use 1 Asterisk instance, all files
will be copied to 'configs/ast1'.

For example, we can see the 'basic-call' test below will use 2 Asterisk
instances.  However, assume both instances have the same extensions.conf file,
instead duplicating data by copying it into 'ast1' and 'ast2', shared
configuration files SHOULD be copied into the root 'configs' directory.

    basic-call/
        configs/
            ast1/
                sip.conf
                ...
            ast2/
                sip.conf
                ...
            extensions.conf
        run-test

Since each Asterisk instance required difference SIP settings, each 'ast%d'
folder will have a different sip.conf file.

d) Test Execution

        The "run-test" executable will be run by a top level application in the
test suite called "runtests.py".  When "run-test" is executed, it will be
provided a standard set of arguments which are defined here:

        -v <Asterisk version>       # Will always be provided

e) Logging, Pass/Fail Reporting

        All test output, including failure details, should be send to STDOUT.
If the test has failed, the "run-test" executable should exit with a non-zero
return code.  A return code of zero is considered a success.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 6) Test Configuration
--------------------------------------------------------------------------------

        Test configuration lives in a file called "test-config.yaml".  The
format for the configuration file is YAML.  More information on YAML can be
found at http://www.yaml.org/.



#
# Example test configuration file - test-config.yaml
#
# All elements are required unless explicitly noted as OPTIONAL.  If marked
# GLOBAL, those elements are only processed if they exist in the top level
# test-config.yaml file, which applies global options across the test.
#

# The global settings section, which defines which test configuration to execute
# and other non-test specific information
global-settings: # GLOBAL
    # The active test configuration.  The value must match a subsequent key
    # in this file, which defines the global settings to apply to the test execution
    # run.
    test-configuration: config-pessimistic # GLOBAL

    # The following sequence defines for any test configuration the available pre-
    # and post-test conditions.  The 'name' field specifies how the test configurations
    # refer to the pre- and post-test conditions in order to activate them.
    condition-definitions: # GLOBAL
            -
                name: 'threads'
                # A pre-test condition, which specifies that the object will be evaluated
                # prior to test execution
                pre:
                    # The fully qualified Python typename of the object to create using
                    # introspection
                    typename: 'asterisk.ThreadTestCondition.ThreadPreTestCondition'
                post:
                    typename: 'asterisk.ThreadTestCondition.ThreadPostTestCondition'
                    # The fully qualified Python typename of the object to pass to the evaluate
                    # function of this object
                    related-type: 'asterisk.ThreadTestCondition.ThreadPreTestCondition'
            -
                name: 'sip-dialogs'
                pre:
                    typename: 'asterisk.SipDialogTestCondition.SipDialogPreTestCondition'
                post:
                    typename: 'asterisk.SipDialogTestCondition.SipDialogPostTestCondition'
            -
                name: 'locks'
                pre:
                    typename: 'asterisk.LockTestCondition.LockTestCondition'
                post:
                    typename: 'asterisk.LockTestCondition.LockTestCondition'
            -
                name: 'file-descriptors'
                pre:
                    typename: 'asterisk.FdTestCondition.FdPreTestCondition'
                post:
                    typename: 'asterisk.FdTestCondition.FdPostTestCondition'
                    related-type: 'asterisk.FdTestCondition.FdPreTestCondition'
            -
                name: 'channels'
                pre:
                    typename: 'asterisk.ChannelTestCondition.ChannelTestCondition'
                post:
                    typename: 'asterisk.ChannelTestCondition.ChannelTestCondition'

# A global test definition.  This name can be anything, but must be referenced
# by the global-settings.test-configuration key.
config-pessimistic: # GLOBAL
    # A list of tests to explicitly exclude from execution.  This overrides the
    # test listsing in the tests.yaml files.
    exclude-tests: # GLOBAL
        # The name of a test to exclude.  Name matching is done using the Python
        # in operator.
        - 'authenticate_invalid_password'
    properties:
        # The test conditions to apply to all tests.  See specific configuration
        # information for the test conditions in the individual test configuration
        # section below.
        testconditions:
            - name: 'threads'
            - name: 'sip-dialogs'
            - name: 'locks'
            - name: 'file-descriptors'
            - name: 'channels'

# The testinfo section contains information that describes the purpose of an
# individual test
testinfo:
    skip : 'Brief reason for skipping test' # OPTIONAL
    summary     : 'Put a short one liner summary of the test here'
    issues      : |
        # List of issue numbers associated with this test
        # OPTIONAL
        - mantis : '12345'
        - mantis : '10101'
    description : |
        'Put a more verbose description of the test here.  This may span
        multiple lines.'

# The properties section contains information about requirements and
# dependencies for this test.
properties:
    minversion : '1.8.0.0' # minimum Asterisk version compatible with this test
    buildoption : 'TEST_FRAMEWORK' # OPTIONAL - Asterisk compilation flag
    maxversion : '10.5.1' # OPTIONAL
    features:
        # List features the Asterisk version under test must support for this test
        # to execute.  All features must be satisfied for the test to run.
        - 'digiumphones'
        - 'cert'
    dependencies : |   # OPTIONAL
        # List dependencies that must be met for this test to run
        #
        # Checking for an 'app' dependency behaves like the 'which' command
        - app : 'bash'
        - app : 'sipp'

        # A 'python' dependency is a python module.  An attempt will be made to
        # import a module by this name to determine whether the dependency is
        # met.
        - python : 'yaml'

        # A 'module' dependency is an Asterisk module that must be loaded by
        # Asterisk in order for this test to execute.  If the module is not loaded,
        # the test will not execute.
        - module : 'app_dial'

        # 'custom' dependency can be anything.  Checking for this dependency is
        # done by calling a corresponding method in the Dependency class in
        # runtests.py.  For example, if the dependency is 'ipv6', then the
        # depend_ipv6() method is called to determine if the dependency is met.
        - custom : 'ipv6'
        - custom : 'fax'
    testconditions: # OPTIONAL
        #
        # List of overrides for pre-test and post-test conditions.  If a condition is
        # defined for a test, the configuration of that condition in the test overrides
        # the setting defined in the global test configuration file.
        #
        -   # Check for thread usage in Asterisk.  Any threads present in Asterisk after test
            # execution - and any threads that were detected prior to test execution
            # that are no longer present - will be flagged as a test error.
            name: 'threads'
            #
            # Disable execution of this condition.  This setting applies to any defined condition.
            # Any other value but 'False' will result in the condition being executed.
            enabled: 'False'
            #
            # Execute the condition, but expect the condition to fail
            expectedResult: 'Fail'
            #
            # The thread test condition allows for certain detected threads to be
            # ignored.  This is a list of the thread names, as reported by the CLI
            # command 'core show threads'
            ignoredThreads:
                - 'netconsole'
                - 'pbx_thread'
        #
        -   # Check for SIP dialog usage.  This looks for any SIP dialogs present
            # in the system before and after a run; if any are present and are not
            # scheduled for destruction, an error is raised.
            name: 'sip-dialogs'
            #
            # In addition to checking for scheduled destruction, a test can request that
            # certain entries should appear in the SIP history.  If the entries do not
            # appear, an error is raised.
            sipHistoryRequirements:
                - 'NewChan'
                - 'Hangup'
        #
        -   # Check for held locks in Asterisk after test execution.  A lock is determined to
            # be in potential error if threads are detected holding mutexes and waiting on
            # other threads that are also holding mutexes.
            name: 'locks'
        #
        -   # Check for active channels in Asterisk.  If active channels are detected, flag
            # an error
            name: 'channels'
            #
            # The number of allowed active channels that can exist when the condition is checked.
            # If the number of channels detected is greater than this value, an error is raised.
            # By default, this value is 0.
            allowedchannels: 1
        #
        -   # Check for active file descriptors in Asterisk.  File descriptors detected before
            # test execution are tracked throughout the test; if any additional file descriptors
            # after test execution are detected, the test condition fails.
            name: 'file-descriptors'
    tags: # OPTIONAL
        #
        # List of tags used to select a subset of tests to run.  A test must have all tags to run.
        #
        -   core # This test is part of the core support level.
        -   voicemail # This test involves voicemail functionality.


--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 7) Tests in Python
--------------------------------------------------------------------------------

        There are some python modules included in lib/python/ which are intended
to help with writing tests in python.  Python code in the testsuite should be
formatted according to PEP8: http://www.python.org/dev/peps/pep-0008/.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 8) Tests in Lua
--------------------------------------------------------------------------------

        The asttest framework included in the asttest directory provides a lot
of functionality to make it easy to write Asterisk tests in Lua.  Take a look at
the asttest README as well as some of the existing Lua tests for more
information.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 9) Custom Tests
--------------------------------------------------------------------------------

        The testsuite supports automatic use of custom tests.  This feature is
activated by creating tests/custom/tests.yaml to list your tests and/or folders
of tests.  Any files created in tests/custom will be ignored by the Asterisk
testsuite repository.  This folder is designed to be used for tests that are
not appropriate for inclusion in the common testsuite.  This can include tests
specific for your business, clients or Asterisk based product.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

================================================================================
================================================================================
