#!/bin/bash

find . -type d -name tmp | grep -vF .svn | xargs -d\\n rm -rf
rm -rf /tmp/asterisk-testsuite /var/tmp/asterisk-testsuite ./logs/* ./fastagi
find -name '__pycache__' -type d -exec rm -rf {} +
find -name '*.pyc' -delete
