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

#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>

#include "asttest/lua.h"
#include "asttest/testsuite.h"

#include "asttest/lua/astlib.h"
#include "asttest/lua/testlib.h"
#include "asttest/lua/proclib.h"

#include LUAFILESYSTEM_HEADER
#include LUASOCKET_HEADER
#include LUAPOSIX_HEADER

lua_State *get_lua_state(struct testsuite *ts, const char *test_name) {
	lua_State *L = luaL_newstate();
	if (!L) {
		goto e_return;
	}

	luaL_openlibs(L);

	/* luad LuaFileSystem */
	lua_pushcfunction(L, luaopen_lfs);
	if (lua_pcall(L, 0, 0, 0)) {
		goto e_print_error;
	}

	/* load LuaSocket */
	lua_pushcfunction(L, luaopen_socket_core);
	if (lua_pcall(L, 0, 0, 0)) {
		goto e_print_error;
	}

	/* load LuaPosix */
	lua_pushcfunction(L, luaopen_posix);
	if (lua_pcall(L, 0, 0, 0)) {
		goto e_print_error;
	}

	/* load the test lib */
	lua_pushcfunction(L, luaopen_testlib);
	lua_pushlightuserdata(L, ts);
	lua_pushstring(L, test_name);
	if (lua_pcall(L, 2, 0, 0)) {
		goto e_print_error;
	}

	/* load the proc lib */
	lua_pushcfunction(L, luaopen_proclib);
	if (lua_pcall(L, 0, 0, 0)) {
		goto e_print_error;
	}

	/* load the asterisk lib */
	lua_pushcfunction(L, luaopen_astlib);
	lua_pushstring(L, ts->asterisk_path);
	if (ts->asterisk_version)
		lua_pushstring(L, ts->asterisk_version);
	else
		lua_pushnil(L);
	if (lua_pcall(L, 2, 0, 0)) {
		goto e_print_error;
	}

	return L;

e_print_error:
	/* we expect an error string on the top of the stack */
	ts_log(ts, test_name, "%s\n", lua_tostring(L, -1));
/*e_close_lua:*/
	lua_close(L);
e_return:
	return NULL;
}

