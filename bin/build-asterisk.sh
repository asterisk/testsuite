#!/bin/bash

PLAN=$1
BUILD_DIR=/srv/bamboo/xml-data/build-dir/${PLAN}

export PATH=/usr/lib/ccache:${PATH}

./configure --enable-dev-mode
make uninstall-all
make menuselect.makeopts
if [ "${PLAN}" = "AST-TRUNK" ] ; then
	sed -i -e 's/MENUSELECT_CFLAGS=/MENUSELECT_CFLAGS=TEST_FRAMEWORK /' menuselect.makeopts
	sed -i -e 's/MENUSELECT_TEST=.*$/MENUSELECT_TEST=/' menuselect.makeopts
fi
make

if [ "${PLAN}" != "AST-TRUNK" ] ; then
	exit 0
fi

echo "*** Installing Asterisk and Sample Configuration ***"
make install
make samples

echo "*** Starting Asterisk ***"
asterisk
sleep 5

echo "*** Executing Unit Tests ***"
asterisk -rx "test execute all"

echo "*** Generating Unit Test Results Output ***"
mkdir ${BUILD_DIR}/test-reports
asterisk -rx "test generate results xml ${BUILD_DIR}/test-reports/unit-test-results.xml"
sleep 3

echo "*** Stopping Asterisk ***"
asterisk -rx "core stop now"
