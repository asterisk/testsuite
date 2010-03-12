#!/bin/sh

BINDIR=/usr/local/bin/bamboo/

svn co http://svn.digium.com/svn/testsuite/asterisk/trunk testsuite
cd testsuite
make install
cd ..
rm -rf testsuite

set -e

${BINDIR}/build-asterisk.sh
