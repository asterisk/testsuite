INSTALL?=install

BINDIR?=/usr/local/bin/bamboo

all:
	@echo "************************************************************"
	@echo "***" 
	@echo "*** Run \"make install\" to install build scripts."
	@echo "***" 
	@echo "************************************************************"

install:
	mkdir -p $(BINDIR)
	for n in bamboo/bin/* ; do $(INSTALL) -m 755 $$n $(BINDIR) ; done
	if [ -d /Library/LaunchDaemons ] ; then $(INSTALL) -m 644 bamboo/mac-osx/com.asterisk.org.asterisk /Library/LaunchDaemons ; fi
