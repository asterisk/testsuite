#! /usr/bin/env python
"""Asterisk testsuite utils 

This module provides access to Asterisk testsuite utility
functions from within python code.

Copyright (C) 2010, Digium, Inc.
Paul Belanger <pabelanger@digium.com>

This program is free software, distributed under the terms of
the GNU General Public License Version 2.
"""

import os
from os import close
from os import remove
from shutil import move
from tempfile import mkstemp

def which(program):
    """Find the executable for a specified program

    Taken from:
    http://stackoverflow.com/questions/377017/test-if-executable-exists-in-python
    """
    def is_exe(fpath):
        """Is this an executable?"""
        return os.path.exists(fpath) and os.access(fpath, os.X_OK)

    fpath, fname = os.path.split(program)
    if fpath:
        if is_exe(program):
            return program

    else:
        for path in os.environ["PATH"].split(os.pathsep):
            exe_file = os.path.join(path, program)
            if is_exe(exe_file):
                return exe_file

    return None

def file_replace_string(file_name, pattern, subst):
    """Replace strings within a file with substr.

    Keyword arguments:
    file_name    filename of the text file within which strings are meant
                 to be replaced
    pattern      string in file which is matched against, removed, and
                 replaced by substr
    subst        string which is substituted for the pattern once the operation
                 is finished
    """
    # Create temp file
    f_handle, abs_path = mkstemp()
    new_file = open(abs_path,'w')
    old_file = open(file_name)
    for line in old_file:
        new_file.write(line.replace(pattern, subst))
    # Close temp file
    new_file.close()
    close(f_handle)
    old_file.close()
    # Remove original file
    remove(file_name)
    # Move new file
    move(abs_path, file_name)

