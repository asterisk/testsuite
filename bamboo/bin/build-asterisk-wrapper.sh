#!/bin/bash

BINDIR=/usr/local/bin/bamboo/

mkdir bamboo
cd bamboo
svn co http://svn.digium.com/svn/testsuite/bamboo/trunk
cd trunk
make install
cd ../..
rm -rf bamboo

set -e

${BINDIR}/build-asterisk.sh $@
