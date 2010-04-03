#!/bin/bash

for n in `find . -type d -name 'tmp' | grep -v ".svn"` ; do rm -rf $n ; done
