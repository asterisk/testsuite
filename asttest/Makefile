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

LUAFILESYSTEM_OBJS=lua/$(LUAFILESYSTEM)/src/lfs.o 
LUASOCKET_OBJS=lua/$(LUASOCKET)/src/luasocket.a
LUAPOSIX_OBJS=lua/$(LUAPOSIX)/lposix.o

LUAFILESYSTEM_HEADER=lua/$(LUAFILESYSTEM)/src/lfs.h
LUASOCKET_HEADER=lua/$(LUASOCKET)/src/luasocket.h
LUAPOSIX_HEADER=lua/$(LUAPOSIX)/lposix.h

LUAPOSIX_LIBS=-lcrypt

# Basic set of sources and flags/libraries/includes
OBJS:=asttest.o lib/lua.o lib/testsuite.o lib/testutils.o
CFLAGS:=-g -c -D_GNU_SOURCE -Wall -I/usr/include/lua5.1 -Iinclude -Ilua
L_MODULES:=$(LUAFILESYSTEM_OBJS) $(LUASOCKET_OBJS) $(LUAPOSIX_OBJS) 
L_LIBS:=$(LUAPOSIX_LIBS)
L_OBJS:=lua/testlib.o lua/astlib.o lua/proclib.o
T_LIBS:=-llua5.1


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

lua/%_lua.h : lua/%.lua tools/mkstring
	luac -o $(basename $<).luac $<
	./tools/mkstring -n $(notdir $(basename $<))_lua -o $@ $(basename $<).luac 

lib/%.o: lib/%.c include/asttest/%.h

# this line does not seem to work
#lua/%.o: lua/%.c lua/%_lua.h include/asttest/lua/%.h

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

lua/testlib.o: lua/testlib.c lua/testlib_lua.h include/asttest/lua/testlib.h
lua/astlib.o: lua/astlib.c lua/astlib_lua.h include/asttest/lua/astlib.h
lua/proclib.o: lua/proclib.c lua/proclib_lua.h include/asttest/lua/proclib.h

$(LUAFILESYSTEM_OBJS): lua/$(LUAFILESYSTEM) lua/lfs-patched.stamp
	$(MAKE) -C lua/$(LUAFILESYSTEM)

lua/lfs-patched.stamp lua/$(LUAFILESYSTEM): lua/$(LUAFILESYSTEM).tar.gz
	tar -C lua -zxf lua/$(LUAFILESYSTEM).tar.gz 
	patch -p1 -d lua/$(LUAFILESYSTEM) < tools/lfs.diff
	touch lua/lfs-patched.stamp

$(LUASOCKET_OBJS): lua/$(LUASOCKET) lua/luasocket-patched.stamp
	$(MAKE) -C lua/$(LUASOCKET)

lua/luasocket-patched.stamp lua/$(LUASOCKET): lua/$(LUASOCKET).tar.gz
	tar -C lua -zxf lua/$(LUASOCKET).tar.gz 
	patch -p1 -d lua/$(LUASOCKET) < tools/luasocket.diff
	touch lua/luasocket-patched.stamp

$(LUAPOSIX_OBJS): lua/$(LUAPOSIX) lua/luaposix-patched.stamp
	$(MAKE) -C lua/$(LUAPOSIX)

lua/luaposix-patched.stamp lua/$(LUAPOSIX): lua/$(LUAPOSIX).tar.gz
	tar -C lua -zxf lua/$(LUAPOSIX).tar.gz 
	patch -p1 -d lua/$(LUAPOSIX) < tools/luaposix.diff
	touch lua/luaposix-patched.stamp

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
test: asttest asterisk
	./asttest tests

clean:
	rm -f asttest $(OBJS) $(M_OBJS) $(C_OBJS) $(G_OBJS) $(N_OBJS) $(L_OBJS)
	rm -f lua/*_lua.h
	rm -f lua/*.luac
	rm -f tools/mkstring
	rm -rf $(ASTDSTDIR)
	-$(MAKE) -C lua/$(LUAFILESYSTEM) clean
	-$(MAKE) -C lua/$(LUASOCKET) clean
	-$(MAKE) -C lua/$(LUAPOSIX) clean

dist-clean: distclean

distclean: clean
	rm -f autoconfig.h config.status config.log makeopts
	rm -rf autom4te.cache
	rm -rf lua/$(LUAFILESYSTEM)
	rm -rf lua/$(LUASOCKET)
	rm -rf lua/$(LUAPOSIX)
	rm -f lua/lfs-patched.stamp
	rm -f lua/luasocket-patched.stamp
	rm -f lua/luaposix-patched.stamp

