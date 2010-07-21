================================================================================
===                                                                          ===
===                           Asterisk Test Suite                            ===
===                                                                          ===
===                         http://www.asterisk.org/                         ===
===                      Copyright (C) 2010, Digium, Inc.                    ===
===                                                                          ===
================================================================================

--------------------------------------------------------------------------------
--- 0) Table of Contents
--------------------------------------------------------------------------------

    Using the Test Suite:
        1) Introduction
        2) Test Suite System Requirements
        3) Running the Test Suite

    Writing Tests:
        4) Test Anatomy
        5) Test Configuration
        6) Tests in Python
        7) Tests in Lua

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

---------------------------------------------------------------------------------
--- 2) Test Suite System Requirements
--------------------------------------------------------------------------------

Required:
        - python >= 2.4
        - python-yaml

Optional (needed by specific tests):
        - bash
        - SIPp
            - Download the latest unstable release
            - http://sipp.sourceforge.net/snapshots/
            - Compile the version with pcap support using "make pcapplay"
        - asttest
            - included with the test suite
        - Python modules
            - starpy
                - http://www.vrplumber.com/programming/starpy/
                - Install starpy from svn trunk:
                  $ svn co https://starpy.svn.sourceforge.net/svnroot/starpy
                  $ cd starpy/trunk
                  # python setup.py install
            - python-twisted
        - pjsua
            - http://www.pjsip.org/download.htm
            - Download and build pjsip from source
              $ ./configure && make dep && make
            - Rename 'pjsua-x86-unknown-linux-gnu' executable found in the
              pjsip-apps/bin/ directory to 'pjsua', and place the 'pjsua'
              executable into a directory located in the execution path.
              $ cp pjsip-apps/bin/pjsua-x86-unknown-linux-gnu /usr/sbin/pjsua 

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

---------------------------------------------------------------------------------
--- 3) Running the Test Suite
--------------------------------------------------------------------------------

Get the Asterisk source tree you want to test:
    $ svn co http://svn.digium.com/svn/asterisk/trunk asterisk-trunk
    $ cd asterisk-trunk

Build it.
    $ ./configure && make

Check out the test suite inside of the Asterisk source tree.  In this case, we
will have the testsuite directory inside of the asterisk-trunk directory.
    $ svn co http://svn.digium.com/svn/testsuite/asterisk/trunk testsuite
    $ cd testsuite

List the tests:
    $ ./runtests.py -l

       ******************************************
       *** Listing the tests will also tell   ***
       *** you which dependencies are missing ***
       ******************************************

Run the tests:
    # ./runtests.py

For more syntax informatino:
    $ ./runtests.py --help

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

-------------------------------------------------------------------------------
--- 4) Test Anatomy
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

        Finally, to have a test included in the test suite, it must be added to
the "tests.yaml" file that lives in the tests directory.  This configuration
file determines the order that the tests are considered for execution by the top
level test suite application.


b) Preconditions

        When the "run-test" application is executed, it can assume that the
system has a fresh install of Asterisk with files installed into their default
locations.  This includes a fresh set of sample configuration files in the
/etc/asterisk directory.


c) Test Execution

        The "run-test" executable will be run by a top level application in the
test suite called "runtests.py".  When "run-test" is executed, it will be
provided a standard set of arguments which are defined here:

        -v <Asterisk version>       # Will always be provided


d) Logging, Pass/Fail Reporting

        All test output, including failure details, should be send to STDOUT.
If the test has failed, the "run-test" executable should exit with a non-zero
return code.  A return code of zero is considered a success.


--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 5) Test Configuration
--------------------------------------------------------------------------------

        Test configuration lives in a file called "test-config.yaml".  The
format for the configuration file is YAML.  More information on YAML can be
found at http://www.yaml.org/.



#
# Example test configuration file - test-config.yaml
#
# All elements are required unless explicitly noted as OPTIONAL
#

# The testinfo section contains information that describes the purpose of the
# test.
testinfo:
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
    minversion : '1.4' # minimum Asterisk version compatible with this test
    maxversion : '1.8' # OPTIONAL
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

        # 'custom' dependency can be anything.  Checking for this dependency is
        # done by calling a corresponding method in the Dependency class in
        # runtests.py.  For example, if the dependency is 'ipv6', then the
        # depend_ipv6() method is called to determine if the dependency is met.
        - custom : 'ipv6'
        - custom : 'fax'



--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 6) Tests in Python
--------------------------------------------------------------------------------

        There are some python modules included in lib/python/ which are intended
to help with writing tests in python.  Python code in the testsuite should be
formatted according to PEP8: http://www.python.org/dev/peps/pep-0008/.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 7) Tests in Lua
--------------------------------------------------------------------------------

        The asttest framework included in the asttest directory provides a lot
of functionality to make it easy to write Asterisk tests in Lua.  Take a look at
the asttest README as well as some of the existing Lua tests for more
information.

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

================================================================================
================================================================================
