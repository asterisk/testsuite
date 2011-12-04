#!/bin/bash

find . -type d -name tmp | grep -vF .svn | xargs -d\\n rm -rf
rm -rf /tmp/asterisk-testsuite
