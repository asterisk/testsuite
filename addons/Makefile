#
# Copyright (C) 2010, Digium, Inc.
# Paul Belanger <pabelanger@digium.com>
#
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.
#

all:

clean: _clean

_clean:

dist-clean: distclean

distclean: _clean
	rm -rf starpy/install.record

install:
	cd starpy; python setup.py install --prefix=~/.local --record install.record

uninstall:
	rm -rf $$(cat starpy/install.record)
