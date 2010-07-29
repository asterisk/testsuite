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

#include "asttest/testsuite.h"

#include "testlib_lua.h"

/*
 * \brief Check if the current test was expected to fail or not.
 * \param L the lua state to use
 * \note This function expects testlib to be loaded, which should always be the
 * case by the time it is called.
 * \return whether the current test was expected to fail or not
 */
int testlib_expected_fail(lua_State *L) {
	int res;
	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_xfail");
	res = lua_toboolean(L, -1);
	lua_pop(L, 1);
	return res;
}

/*
 * \brief Push the current testsuite on the stack and return a pointer to it.
 * \param L the lua state to use
 */
static struct testsuite *push_ts(lua_State *L) {
	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_ts");
	return lua_touserdata(L, -1);
}

/*
 * \brief Push the current test's name on the stack and return a pointer to it.
 * \param L the lua state to use
 */
static const char *get_test_name(lua_State *L) {
	const char *c;
	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_name");
	c = lua_tostring(L, -1);
	lua_pop(L, 1);
	return c;
}

/*
 * \brief [lua_CFunction] Log a message for the current test.
 * \param message [lua] the string to log
 */
static int lua_ts_log(lua_State *L) {
	const char *string = luaL_checkstring(L, 1);
	struct testsuite *ts = push_ts(L);
	const char *name = get_test_name(L);

	ts_log(ts, name, "%s", string);

	return 0;
}

/*
 * \brief [lua_CFunction] Notify the test driver that this test is expected to
 * fail.
 */
static int lua_xfail(lua_State *L) {
	lua_pushboolean(L, 1);
	lua_setfield(L, LUA_REGISTRYINDEX, "testlib_xfail");
	return 0;
}

static luaL_Reg testlib[] = {
	{"log", lua_ts_log},
	{"xfail", lua_xfail},
	{NULL, NULL},
};

int luaopen_testlib(lua_State *L) {
	const char *test_name;
	struct testsuite *ts;

	luaL_checktype(L, 1, LUA_TLIGHTUSERDATA);
	ts = lua_touserdata(L, 1);
	test_name = luaL_checkstring(L, 2);

	/* set up some registry values */
	lua_pushlightuserdata(L, ts);
	lua_setfield(L, LUA_REGISTRYINDEX, "testlib_ts");

	lua_pushstring(L, test_name);
	lua_setfield(L, LUA_REGISTRYINDEX, "testlib_name");
	
	lua_pushboolean(L, 0);
	lua_setfield(L, LUA_REGISTRYINDEX, "testlib_xfail");

	/* register our functions */
	luaL_register(L, "test", testlib);
	lua_pushstring(L, test_name);
	lua_setfield(L, -2, "name");
	lua_pop(L, 1);
	
	/* load the lua portion of the lib */
	if (luaL_loadbuffer(L, testlib_lua, sizeof(testlib_lua), "testlib"))
		goto e_lua_error;
	lua_pushstring(L, "test");
	if (lua_pcall(L, 1, 1, 0))
		goto e_lua_error;

	return 1;

e_lua_error:
	/* format the error message a little */
	lua_pushstring(L, "error loading test library: ");
	lua_insert(L, -2);
	lua_concat(L, 2);
	return lua_error(L);
}

