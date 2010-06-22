#
# Asterisk -- A telephony toolkit for Linux.
# 
# Makefile for asttest
#
# Copyright (C) 2005-2008, Digium, Inc.
#
# Matthew Nicholson <mnicholson@digium.com>
#
# This program is free software, distributed under the terms of
# the GNU General Public License
#

# even though we could use '-include makeopts' here, use a wildcard
# lookup anyway, so that make won't try to build makeopts if it doesn't
# exist (other rules will force it to be built if needed)
ifneq ($(wildcard makeopts),)
  include makeopts
endif

.PHONY: clean dist-clean distclean test check asterisk

INSTALL?=install
DESTDIR?=
BINDIR?=/usr/bin

ASTSRCDIR ?= ../
ASTDSTDIR ?= $(PWD)/asterisk


LUAFILESYSTEM=luafilesystem-1.4.2
LUASOCKET=luasocket-2.0.2
LUAPOSIX=luaposix-5.1.4

LUAFILESYSTEM_OBJS=lib/lua/$(LUAFILESYSTEM)/src/lfs.o 
LUASOCKET_OBJS=lib/lua/$(LUASOCKET)/src/luasocket.a
LUAPOSIX_OBJS=lib/lua/$(LUAPOSIX)/lposix.o

LUAFILESYSTEM_HEADER=lib/lua/$(LUAFILESYSTEM)/src/lfs.h
LUASOCKET_HEADER=lib/lua/$(LUASOCKET)/src/luasocket.h
LUAPOSIX_HEADER=lib/lua/$(LUAPOSIX)/lposix.h

LUAPOSIX_LIBS=-lcrypt

# Basic set of sources and flags/libraries/includes
OBJS:=asttest.o lib/lua.o lib/testsuite.o lib/testutils.o
CFLAGS:=-g -c -D_GNU_SOURCE -Wall `pkg-config --cflags lua5.1 2> /dev/null || pkg-config --cflags lua 2> /dev/null` -Iinclude
L_MODULES:=$(LUAFILESYSTEM_OBJS) $(LUASOCKET_OBJS) $(LUAPOSIX_OBJS) 
L_LIBS:=$(LUAPOSIX_LIBS)
L_OBJS:=lib/lua/testlib.o lib/lua/astlib.o lib/lua/proclib.o
T_LIBS:=`pkg-config --libs lua5.1 2> /dev/null || pkg-config --libs lua 2> /dev/null || echo -llua -lm -ldl`


all: asttest

#$(OBJS) $(C_OBJS): autoconfig.h menuselect.h
#
#makeopts autoconfig.h: autoconfig.h.in makeopts.in
#	@./configure $(CONFIGURE_SILENT) CC= LD= AR= CFLAGS=
#
#ifdef C_OBJS
#menuselect_curses.o: CFLAGS+=$(C_INCLUDE)
#cmenuselect: $(OBJS) $(C_OBJS)
#	$(CC) -o $@ $^ $(C_LIBS)
#else
#cmenuselect:
#endif
#
#ifdef G_OBJS
#menuselect_gtk.o: CFLAGS+=$(G_INCLUDE)
#gmenuselect: $(OBJS) $(G_OBJS)
#	$(CC) -o $@ $^ $(G_LIBS)
#else
#gmenuselect:
#endif
#
#ifdef N_OBJS
#menuselect_newt.o: CFLAGS+=$(N_INCLUDE)
#nmenuselect: $(OBJS) $(N_OBJS)
#	$(CC) -o $@ $^ $(N_LIBS)
#else
#nmenuselect:
#endif

lib/lua/%_lua.h : lib/lua/%.lua tools/mkstring
	luac -o $(basename $<).luac $<
	./tools/mkstring -n $(notdir $(basename $<))_lua -o $@ $(basename $<).luac 

lib/%.o: lib/%.c include/asttest/%.h

# this line does not seem to work
#lib/lua/%.o: lib/lua/%.c lib/lua/%_lua.h include/asttest/lua/%.h

asterisk:
	cd $(ASTSRCDIR) && ./configure --enable-dev-mode \
		--prefix=$(ASTDSTDIR)/usr \
		--sysconfdir=$(ASTDSTDIR)/etc \
		--localstatedir=$(ASTDSTDIR)/var
	$(MAKE) -C $(ASTSRCDIR) install
	$(MAKE) -C $(ASTSRCDIR) samples

lib/testsuite.o: lib/testsuite.c include/asttest/testsuite.h include/asttest/asttest.h
lib/testutils.o: lib/testutils.c include/asttest/testutils.h include/asttest/asttest.h include/asttest/testsuite.h include/asttest/lua.h

lib/lua.o: lib/lua.c $(L_MODULES) include/asttest/lua.h include/asttest/testsuite.h include/asttest/lua/*.h
	$(CC) $(CFLAGS) -o $@ \
	-DLUAFILESYSTEM_HEADER=\"../$(LUAFILESYSTEM_HEADER)\" \
	-DLUASOCKET_HEADER=\"../$(LUASOCKET_HEADER)\" \
	-DLUAPOSIX_HEADER=\"../$(LUAPOSIX_HEADER)\" \
       	$<

lib/lua/testlib.o: lib/lua/testlib.c lib/lua/testlib_lua.h include/asttest/lua/testlib.h
lib/lua/astlib.o: lib/lua/astlib.c lib/lua/astlib_lua.h include/asttest/lua/astlib.h
lib/lua/proclib.o: lib/lua/proclib.c lib/lua/proclib_lua.h include/asttest/lua/proclib.h

$(LUAFILESYSTEM_OBJS): lib/lua/$(LUAFILESYSTEM) lib/lua/lfs-patched.stamp
	$(MAKE) -C lib/lua/$(LUAFILESYSTEM)

lib/lua/lfs-patched.stamp lib/lua/$(LUAFILESYSTEM): lib/lua/$(LUAFILESYSTEM).tar.gz tools/lfs.diff
	rm -rf lib/lua/$(LUAFILESYSTEM)
	tar -C lib/lua -zxf lib/lua/$(LUAFILESYSTEM).tar.gz 
	patch -p1 -d lib/lua/$(LUAFILESYSTEM) < tools/lfs.diff
	touch lib/lua/lfs-patched.stamp

$(LUASOCKET_OBJS): lib/lua/$(LUASOCKET) lib/lua/luasocket-patched.stamp
	$(MAKE) -C lib/lua/$(LUASOCKET)

lib/lua/luasocket-patched.stamp lib/lua/$(LUASOCKET): lib/lua/$(LUASOCKET).tar.gz tools/luasocket.diff
	rm -rf lib/lua/$(LUASOCKET)
	tar -C lib/lua -zxf lib/lua/$(LUASOCKET).tar.gz 
	patch -p1 -d lib/lua/$(LUASOCKET) < tools/luasocket.diff
	touch lib/lua/luasocket-patched.stamp

$(LUAPOSIX_OBJS): lib/lua/$(LUAPOSIX) lib/lua/luaposix-patched.stamp
	$(MAKE) -C lib/lua/$(LUAPOSIX)

lib/lua/luaposix-patched.stamp lib/lua/$(LUAPOSIX): lib/lua/$(LUAPOSIX).tar.gz tools/luaposix.diff
	rm -rf lib/lua/$(LUAPOSIX)
	tar -C lib/lua -zxf lib/lua/$(LUAPOSIX).tar.gz 
	patch -p1 -d lib/lua/$(LUAPOSIX) < tools/luaposix.diff
	touch lib/lua/luaposix-patched.stamp

asttest: asttest.c $(OBJS) $(T_OBJS) $(L_OBJS) include/asttest/asttest.h
	$(CC) -o $@ $(OBJS) $(L_OBJS) $(T_LIBS) $(L_MODULES) $(L_LIBS)

tools/mkstring: tools/mkstring.c
	$(CC) -D_GNU_SOURCE -Wall -o $@ $^

install: asttest
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 asttest $(DESTDIR)$(BINDIR)

uninstall:
	rm -f $(DESTDIR)$(BINDIR)/asttest

check: test
tests: test
test: asttest
	LUA_PATH=$(PWD)/../lib/lua/?.lua\;\; \
	LUA_CPATH=$(PWD)/../lib/lua/\?.so\;\; \
	./asttest self-tests

clean:
	rm -f asttest $(OBJS) $(M_OBJS) $(C_OBJS) $(G_OBJS) $(N_OBJS) $(L_OBJS)
	rm -f lib/lua/*_lua.h
	rm -f lib/lua/*.luac
	rm -f tools/mkstring
	rm -rf $(ASTDSTDIR)
	-$(MAKE) -C lib/lua/$(LUAFILESYSTEM) clean
	-$(MAKE) -C lib/lua/$(LUASOCKET) clean
	-$(MAKE) -C lib/lua/$(LUAPOSIX) clean

dist-clean: distclean

distclean: clean
	rm -f autoconfig.h config.status config.log makeopts
	rm -rf autom4te.cache
	rm -rf lib/lua/$(LUAFILESYSTEM)
	rm -rf lib/lua/$(LUASOCKET)
	rm -rf lib/lua/$(LUAPOSIX)
	rm -f lib/lua/lfs-patched.stamp
	rm -f lib/lua/luasocket-patched.stamp
	rm -f lib/lua/luaposix-patched.stamp

