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
	(cd starpy; python3 setup.py install --prefix=~/.local --record install.record)

uninstall:
	rm -rf $$(cat starpy/install.record)

update:
	@if [ -d starpy ]; then \
		cd starpy; \
		if [ `git config --get remote.origin.url` = https://github.com/asterisk-org/starpy.git ]; then \
			git remote set-url origin https://github.com/asterisk/starpy.git https://github.com/asterisk-org/starpy.git; \
		fi; \
		git checkout 1.1; \
		git pull; \
	else \
		git clone https://github.com/asterisk/starpy.git; \
		git checkout 1.1; \
	fi
