#!/bin/bash

BINDIR=/usr/local/bin/bamboo/

mkdir testsuite
cd testsuite
svn co http://svn.digium.com/svn/testsuite/asterisk/trunk
cd trunk
make install
cd ../..
rm -rf testsuite

set -e

${BINDIR}/build-asterisk.sh $@
