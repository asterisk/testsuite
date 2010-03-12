#!/bin/bash

PLAN=$1
BUILD_DIR=/srv/bamboo/xml-data/build-dir/${PLAN}
TEST_RESULTS_DIR=${BUILD_DIR}/test-reports

export PATH=/usr/lib/ccache:${PATH}

if [ -f "main/test.c" ] ; then
	UNIT_TESTS=yes
else
	UNIT_TESTS=no
fi

set -e

make distclean
./configure --enable-dev-mode
make uninstall-all
make menuselect.makeopts
if [ "${UNIT_TESTS}" = "yes" ] ; then
	menuselect/menuselect --enable TEST_FRAMEWORK menuselect.makeopts
	menuselect/menuselect --enable-category MENUSELECT_TEST menuselect.makeopts
fi
make

if [ -f doc/core-en_US.xml ] ; then
	echo "*** Validating XML documentation ***"
	make validate-docs
fi

if [ "${UNIT_TESTS}" = "yes" ] ; then
	echo "*** Installing Asterisk and Sample Configuration ***"
	WGET_EXTRA_ARGS=--quiet make install
	make samples

	echo "*** Starting Asterisk ***"
	asterisk
	sleep 5

	echo "*** Executing Unit Tests ***"
	asterisk -rx "test execute all"
	sleep 5

	if [ ! -d ${TEST_RESULTS_DIR} ] ; then
		mkdir ${TEST_RESULTS_DIR}
	fi

	echo "*** Generating Unit Test Results Output ***"
	asterisk -rx "test generate results xml ${TEST_RESULTS_DIR}/unit-test-results.xml"
	sleep 5

	echo "*** Stopping Asterisk ***"
	asterisk -rx "core stop now"
fi

if [ "${PLAN}" = "AST-TRUNK" ] ; then
	# Only run test suite on trunk for now, until Asterisk version handling
	# is implemented in the test suite
	echo "*** Running external test suite ***"
	svn co http://svn.digium.com/svn/testsuite/asterisk/trunk testsuite
	cd testsuite
	./run-tests.py
	cp *.xml ../test-reports
fi

echo "*** Test Results: ***"
ls -l ${TEST_RESULTS_DIR}
cat ${TEST_RESULTS_DIR}/*.xml
