#
# Copyright (C) 2010, Digium, Inc.
# Paul Belanger <pabelanger@digium.com>
#
# This program is free software, distributed under the terms of
# the GNU General Public License Version 2.
#

all:
	@if [ ! -d starpy ]; then \
		echo "starpy/ does not exist.  Run \`make update\` to checkout via git."; \
	else \
		echo "Run \`make install\`."; \
	fi

clean: _clean

_clean:

dist-clean: distclean

distclean: _clean
	rm -rf starpy/install.record

install:
	(cd starpy; python setup.py install --prefix=~/.local --record install.record)

uninstall:
	rm -rf $$(cat starpy/install.record)

update:
	@if [ -d starpy ]; then \
		cd starpy; \
		if [ `git config --get remote.origin.url` = git://github.com/asterisk-org/starpy.git ]; then \
			git remote set-url origin git://github.com/asterisk/starpy.git git://github.com/asterisk-org/starpy.git; \
		fi; \
		git pull; \
	else \
		git clone git://github.com/asterisk/starpy.git; \
	fi
