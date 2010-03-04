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

#ifndef ASTTEST_LUA_H
#define ASTTEST_LUA_H

#include <lua.h>

#include "asttest/testsuite.h"

#include "asttest/lua/testlib.h"

lua_State *get_lua_state(struct testsuite *ts, const char *test_name);

#endif
