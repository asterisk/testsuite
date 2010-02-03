INSTALL?=install

BINDIR?=/usr/local/bin/bamboo

all:
	@echo "************************************************************"
	@echo "***" 
	@echo "*** Run \"make install\" to install build scripts."
	@echo "***" 
	@echo "************************************************************"

install:
	mkdir -p /usr/local/bin/bamboo
	for n in bin/* ; do $(INSTALL) -m 755 $$n $(BINDIR) ; done
