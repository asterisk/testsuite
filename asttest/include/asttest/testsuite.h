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

#ifndef ASTTEST_TESTSUITE_H
#define ASTTEST_TESTSUITE_H

#include "asttest/asttest.h"

struct testsuite {
	unsigned int pass;
	unsigned int fail;
	unsigned int xfail;
	unsigned int xpass;
	unsigned int skip;
	unsigned int error;
	unsigned int total;
	FILE *log;
	char asterisk_path[PATH_MAX];
	unsigned int single_test_mode:1;
};

enum ts_result {
	TS_PASS,
	TS_FAIL,
	TS_XFAIL,
	TS_XPASS,
	TS_SKIP,
	TS_ERROR,
};

int ts_init(struct testsuite *ts, const char *path, struct asttest_opts *opts);
int ts_init_single(struct testsuite *ts, struct asttest_opts *opts);
void ts_cleanup(struct testsuite *ts);

void ts_print(struct testsuite *ts);

int ts_log_va(struct testsuite *ts, const char *test_name, const char *fmt, va_list ap);
int __attribute__((format(printf, 3, 4))) ts_log(struct testsuite *ts, const char *test_name, const char *fmt, ...);

enum ts_result ts_pass(struct testsuite *ts, const char *test_name);
enum ts_result ts_fail(struct testsuite *ts, const char *test_name);
enum ts_result ts_xpass(struct testsuite *ts, const char *test_name);
enum ts_result ts_xfail(struct testsuite *ts, const char *test_name);
enum ts_result ts_skip(struct testsuite *ts, const char *test_name);
enum ts_result ts_error(struct testsuite *ts, const char *test_name);

#endif
