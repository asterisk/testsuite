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
static const char *push_test_name(lua_State *L) {
	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_name");
	return lua_tostring(L, -1);
}

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
 * \brief Run the atexit functions.
 * \param L the lua state to use
 * \param result_index the index where the test results are located
 *
 * This function runs all of the atexit functions in the order they were
 * registered.  These functions may change the result of the test.  Any errors
 * that are encountered are logged.
 *
 * \note This function expects testlib to be loaded, which should always be the
 * case by the time it is called.
 * \warn The old results are removed from the stack when new results are pushed.
 * \return 0 on success, non zero if new test results have been pushed to the stack.
 */
int testlib_atexit(lua_State *L, int result_index) {
	int funcs, res, new_result = 0;
	struct testsuite *ts;
	const char *name;

	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_atexit");
	funcs = lua_gettop(L);

	lua_pushnil(L);
	while (lua_next(L, funcs)) {
		lua_pushvalue(L, result_index);

		if ((res = lua_pcall(L, 1, 0, 0))) {
			if (lua_isstring(L, -1)) {
				/* error */
				ts = push_ts(L);
				name = push_test_name(L);
				ts_log(ts, name, "atexit error: %s\n", lua_tostring(L, -3));

				/* name, ts, and the error */
				lua_pop(L, 3);
			} else if (lua_type(L, -1) == LUA_TTABLE) {
				/* got a new result */
				if (new_result) {
					/* remove the old new result */
					lua_remove(L, new_result);
					funcs -= 1;
				}
				/* move the new results under 'funcs' in the stack */
				lua_insert(L, funcs);
				new_result = funcs;
				funcs += 1;
			} else {
				/* got some other error value returned, probably a missing test result */
				ts = push_ts(L);
				name = push_test_name(L);
				ts_log(ts, name, "atexit error: missing test result\n");

				/* name, ts, and the error */
				lua_pop(L, 3);
			}
		}
	}

	/* remove the atexit functions */
	lua_pop(L, 1);

	return new_result;
}

/*
 * \brief This function will turn lua errors into result tables and process
 * unknown results into result tables.
 * \param L the lua state to use
 * \note This function expects the result/error to be on the top of the stack.
 */
void testlib_preprocess_result(lua_State *L) {
	int result_index = lua_gettop(L);
	if (lua_isstring(L, -1)) {
		/* error string */
		lua_newtable(L);

		lua_pushliteral(L, "error");
		lua_setfield(L, -2, "result");

		lua_pushvalue(L, result_index);
		lua_setfield(L, -2, "reason");

		lua_remove(L, result_index);
	} else if (lua_type(L, -1) == LUA_TTABLE) {
		/* do nothing */
	} else {
		/* unknown error type, discard it */
		lua_pop(L, 1);
		lua_newtable(L);

		lua_pushliteral(L, "error");
		lua_setfield(L, -2, "result");

		lua_pushliteral(L, "missing test result");
		lua_setfield(L, -2, "reason");
	}
}

/*
 * \brief Push the default test result to the stack (pass is the default).
 * \param L the lua state to use
 */
void testlib_default_result(lua_State *L) {
	lua_newtable(L);

	lua_pushliteral(L, "pass");
	lua_setfield(L, -2, "result");
}

/*
 * \brief [lua_CFunction] Log a message for the current test.
 * \param message [lua] the string to log
 */
static int lua_ts_log(lua_State *L) {
	const char *string = luaL_checkstring(L, 1);
	struct testsuite *ts = push_ts(L);
	const char *name = push_test_name(L);

	ts_log(ts, name, "%s", string);

	lua_pop(L, 2); /* pop the test name and ts */

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

/*
 * \brief Add a function to the end of the atexit table.
 *
 * Each atexit function that is called is passed a table containing the result
 * of the current test in the following form.
 *
 * \code
 * table = {
 *    result = "pass" or "fail" or "skip" or "error";
 *    reason = nil or "reason string";
 * }
 * \endcode
 *
 * At exit functions can alter the test result using the same method test
 * results are returned from a test (pass(), fail(), etc.).  All atexit
 * functions are passed the original test result, not any modified results.
 * The last modified test result returned will be passed to the testsuite
 * engine.
 */
static int lua_atexit(lua_State *L) {
	luaL_checktype(L, 1, LUA_TFUNCTION);

	lua_getglobal(L, "table");
	if (lua_isnil(L, -1)) {
		lua_pop(L, 1);
		return luaL_error(L, "error running table.insert, 'table' lib not found");
	}

	lua_getfield(L, -1, "insert");
	if (lua_isnil(L, -1)) {
		lua_pop(L, 2);
		return luaL_error(L, "error running table.insert, 'insert' not found in 'table' lib");
	}

	/* remove the 'table' table from the stack */
	lua_remove(L, -2);

	/* call table.insert to add the function to the atexit table */
	lua_getfield(L, LUA_REGISTRYINDEX, "testlib_atexit");
	lua_pushvalue(L, 1);
	lua_call(L, 2, 0);
	return 0;
}

static luaL_Reg testlib[] = {
	{"log", lua_ts_log},
	{"xfail", lua_xfail},
	{"atexit", lua_atexit},
	{NULL, NULL},
};

int luaopen_testlib(lua_State *L) {
	const char *test_name;
	struct testsuite *ts;

	luaL_checktype(L, 1, LUA_TLIGHTUSERDATA);
	ts = lua_touserdata(L, 1);
	test_name = luaL_checkstring(L, 2);

	/* set up atexit table */
	lua_newtable(L);
	lua_setfield(L, LUA_REGISTRYINDEX, "testlib_atexit");

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

