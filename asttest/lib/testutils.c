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

#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <dirent.h>
#include <libgen.h>

#include <lua.h>
#include <lauxlib.h>
#include <lualib.h>

#include "asttest/asttest.h"
#include "asttest/lua.h"
#include "asttest/testsuite.h"
#include "asttest/testutils.h"

/*
 * \brief Check if the given result string equals the string stored at the 
 * given index.
 * \param L the lua state to use
 * \param result_index the index of the result string
 * \param result_string the result string to check for equality with the string 
 * at the given index
 */
static int result_equals(lua_State *L, int result_index, const char *result_string) {
	int res;
	lua_pushstring(L, result_string);
	res = lua_equal(L, -1, result_index);
	lua_pop(L, 1);
	return res;
}

/*
 * \brief Process the result of a test.
 * \param ts the current test suite
 * \param L the lua state the test was run in
 *
 * This function expects to be called after luaL_dofile/lua_pcall and will 
 * analyze the result of running the test.  The testing framework will pass a 
 * special table containg the test result to lua_error() that is used by this 
 * function.
 *
 * The table is expected in the following format:
 *
 * \code
 * table = {
 *    result = "pass" or "fail" or "skip" or "error";
 *    reason = nil or "reason string";
 * }
 * \endcode
 */
static enum ts_result process_test_result(struct testsuite *ts, const char *test_name, lua_State *L) {
	enum ts_result res = TS_ERROR;

	testlib_preprocess_result(L);

	if (lua_type(L, -1) == LUA_TTABLE) {
		int result_table = lua_gettop(L);
		int reason_string = 0;
		int test_result = 0;

		lua_getfield(L, result_table, "reason");
		if (!lua_isnil(L, -1) && lua_isstring(L, -1))
			reason_string = lua_gettop(L);
		else
			lua_pop(L, 1);

		lua_getfield(L, result_table, "result");
		if (lua_isnil(L, -1)) {
			lua_pop(L, 1);
			ts_log(ts, test_name, "error reading test result\n");
			res = ts_error(ts, test_name);
		} else {
			test_result = lua_gettop(L);

			if (reason_string)
				ts_log(ts, test_name, "%s\n", lua_tostring(L, reason_string));

			if (result_equals(L, test_result, "pass")) {
				if (testlib_expected_fail(L))
					res = ts_xpass(ts, test_name);
				else
					res = ts_pass(ts, test_name);
			} else if (result_equals(L, test_result, "fail")) {
				if (testlib_expected_fail(L))
					res = ts_xfail(ts, test_name);
				else
					res = ts_fail(ts, test_name);
			} else if (result_equals(L, test_result, "skip")) {
				res = ts_skip(ts, test_name);
			} else if (result_equals(L, test_result, "error")) {
				res = ts_error(ts, test_name);
			} else {
				ts_log(ts, test_name, "unknown result '%s'\n", lua_tostring(L, test_result));
				res = ts_error(ts, test_name);
			}
		}

		if (test_result)
			lua_remove(L, test_result);
		if (reason_string)
			lua_remove(L, reason_string);

		lua_pop(L, 1);
	} else {
		/* this should never happen, testlib_preprocess_result() should
		 * convert any values to proper result tables for us */
		lua_pop(L, 1);
		ts_log(ts, test_name, "missing test result\n");
		res = ts_error(ts, test_name);
	}

	return res;
}

static void print_test_name(struct testsuite *ts, const char *test_name) {
	int len, i;

	/* first print a number */
	len = printf("%d.", ts->total + 1);

	/* pad the number printed */
	for (i = 4 - len; i > 0; i--) {
		printf(" ");
	}

	/* now print the test name */
	len = printf(" %s ", test_name);

	/* now pad the test name */
	for (i = 31 - len; i > 0; i--) {
		printf(" ");
	}

	fflush(stdout);
}

static void print_test_result(enum ts_result result) {
	switch (result) {
		case TS_PASS:
			printf("pass\n");
			break;
		case TS_FAIL:
			printf("fail\n");
			break;
		case TS_XPASS:
			printf("xpass\n");
			break;
		case TS_XFAIL:
			printf("xfail\n");
			break;
		case TS_SKIP:
			printf("skip\n");
			break;
		case TS_ERROR:
			printf("error\n");
			break;
		default:
			printf("unknown\n");
			break;
	}

	fflush(stdout);
}

static enum ts_result run_test(struct testsuite *ts, const char *test_name, const char *test_dir_path) {
	lua_State *L;
	char original_path[PATH_MAX];
	enum ts_result result;
	int result_index;

	if (!getcwd(original_path, PATH_MAX)) {
		ts_log(ts, test_name, "internal error storing current path, PATH_MAX is too small\n");
		return ts_error(ts, test_name);
	}

	if (chdir(test_dir_path)) {
		ts_log(ts, test_name, "error changing to test dir: %s\n", strerror(errno));
		return ts_error(ts, test_name);
	}

	if (!(L = get_lua_state(ts, test_name))) {
		ts_log(ts, test_name, "internal error, cannot run test\n");
		if (chdir(original_path))
			ts_log(ts, test_name, "additionaly, there was an error changing directories, this may cause further errors (%s)\n", strerror(errno));
		return ts_error(ts, test_name);
	}

	if (!luaL_dofile(L, "test.lua")) {
		/* we got no explicit result, consider it a pass for now */
		testlib_default_result(L);
	}

	/* run our atexit functions */
	testlib_preprocess_result(L);
	result_index = lua_gettop(L);
	if (testlib_atexit(L, result_index)) {
		lua_remove(L, result_index);
	}

	/* process the test result */
	result = process_test_result(ts, test_name, L);

	if (chdir(original_path))
		ts_log(ts, test_name, "error changing directories, this may cause further errors (%s)\n", strerror(errno));

	lua_close(L);
	return result;
}

static int is_directory(const char *dir) {
	struct stat st;
	if (lstat(dir, &st)) {
		return 0;
	}

	return S_ISDIR(st.st_mode);
}

static int ignored_dir(const char *dir) {
	char *dir_dup = strdup(dir);  /* dup the string as basename may modify it */
	char *base_dir = basename(dir_dup);
	int res = 0;

	if (base_dir[0] == '.') {
		res = 1;
	}

	free(dir_dup);
	return res;
}

int process_single_test(struct asttest_opts *opts) {
	struct testsuite ts;
	int res = 0;

	if (ts_init_single(&ts, opts)) {
		printf("Error running test\n");
		return 1;
	}

	run_test(&ts, opts->single_test_mode, opts->single_test_mode);
	if (ts.fail || ts.xpass || ts.error) {
		res = 1;
	}

	ts_cleanup(&ts);

	return res;
}

int process_test_dir(const char *path, struct asttest_opts *opts) {
	DIR *main_dir = opendir(path);
	char full_path[PATH_MAX];
	struct testsuite ts;
	struct dirent *ent;
	enum ts_result result;
	int res = 0;

	printf("Processing tests in '%s':\n", path);

	if (!main_dir) {
		fprintf(stderr, "Error opening path '%s': %s\n", path, strerror(errno));
		return 1;
	}

	ts_init(&ts, path, opts);

	while ((ent = readdir(main_dir))) {
		snprintf(full_path, sizeof(full_path), "%s/%s", path, ent->d_name);
		if (is_directory(full_path) && !ignored_dir(full_path)) {
			print_test_name(&ts, ent->d_name);
			result = run_test(&ts, ent->d_name, full_path);
			print_test_result(result);
		}
	}
	closedir(main_dir);

	printf("\n");
	ts_print(&ts);

	/* consider this run a failure if any tests failed or passed
	 * unexpectedly */
	if (ts.fail || ts.xpass)
		res = 1;

	if (opts->warn_on_error && ts.error) {
		printf("\n***WARNING: some tests failed to run, see log for details\n");
	} else if (ts.error) {
		/* signal a failure */
		res = 1;
	}

	ts_cleanup(&ts);
	return res;
}

