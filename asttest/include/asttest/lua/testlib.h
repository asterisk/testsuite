/*
 * Asterisk -- An open source telephony toolkit.
 *
 * Copyright (C) 1999 - 2008, Digium, Inc.
 *
 * Matthew Nicholson <mnicholson@digium.com>
 *
 * See http://www.asterisk.org for more information about
 * the Asterisk project. Please do not directly contact
 * any of the maintainers of this project for assistance;
 * the project provides a web site, mailing lists and IRC
 * channels for your use.
 *
 * This program is free software, distributed under the terms of
 * the GNU General Public License Version 2. See the LICENSE file
 * at the top of the source tree.
 */

#ifndef ASTTEST_LUA_TESTLIB_H
#define ASTTEST_LUA_TESTLIB_H

#include <lua.h>

int testlib_expected_fail(lua_State *L);
int testlib_atexit(lua_State *L, int result_index);
int testlib_preprocess_result(lua_State *L);
int testlib_default_result(lua_State *L);

int luaopen_testlib(lua_State *L);

#endif
