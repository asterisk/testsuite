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

--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

--------------------------------------------------------------------------------
--- 1) Introduction
--------------------------------------------------------------------------------

        Automated testing for Asterisk is approached from two directions.  The
first is bottom-up unit testing.  Those tests are implemented within Asterisk in
the C programming language, using the Asterisk C APIs.  These tests are enabled
by turning on the TEST_FRAMEWORK compile time option in menuselect.  The CLI
commands related to the test framework all begin with "test".

        The second approach is top down using tests developed outside of
Asterisk.  This test suite is the collection of top-down functionality tests.
The test suite is made up as a collection of scripts that test some portion of
Asterisk functionality given a set of preconditions, and then provide a
pass/fail result via a predefined method of doing so.

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
        - asttest

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

Run the tests:
    # ./runtests.py

For more syntax informatino:
    $ ./runtests.py --hep

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



--------------------------------------------------------------------------------
--------------------------------------------------------------------------------

================================================================================
================================================================================
