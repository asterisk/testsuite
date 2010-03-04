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

#include "asttest/asttest.h"
#include "asttest/testsuite.h"

int ts_init(struct testsuite *ts, const char *path, struct asttest_opts *opts) {
	char log_path[PATH_MAX];
	char cwd[PATH_MAX];
	
	memset(ts, 0, sizeof(struct testsuite));
	
	snprintf(log_path, sizeof(log_path), "%s/%s", path, opts->log_filename);

	ts->log = fopen(log_path, "w");
	if (!ts->log) {
		fprintf(stderr, "Error opening log file for writing (%s): %s\n", log_path, strerror(errno));
		goto e_return;
	}

	/* make asterisk_path absolute */
	if (opts->asterisk_path[0] == '/') {
		/* path starts with '/' we will assume it is absolute */
		snprintf(ts->asterisk_path, sizeof(ts->asterisk_path), "%s", opts->asterisk_path);
	} else {
		if (!getcwd(cwd, sizeof(cwd))) {
			fprintf(stderr, "Error determining the current working directory\n");
			goto e_close_log;
		}

		snprintf(ts->asterisk_path, sizeof(ts->asterisk_path), "%s/%s", cwd, opts->asterisk_path);
	}

	return 0;

e_close_log:
	fclose(ts->log);
e_return:
	return 1;
}

int ts_init_single(struct testsuite *ts, struct asttest_opts *opts) {
	char cwd[PATH_MAX];

	memset(ts, 0, sizeof(struct testsuite));

	ts->log = stdout;
	ts->single_test_mode = 1;

	/* make asterisk_path absolute */
	if (opts->asterisk_path[0] == '/') {
		/* path starts with '/' we will assume it is absolute */
		snprintf(ts->asterisk_path, sizeof(ts->asterisk_path), "%s", opts->asterisk_path);
	} else {
		if (!getcwd(cwd, sizeof(cwd))) {
			printf("Error determining the current working directory\n");
			goto e_return;
		}

		snprintf(ts->asterisk_path, sizeof(ts->asterisk_path), "%s/%s", cwd, opts->asterisk_path);
	}

	return 0;

e_return:
	return 1;
}

void ts_cleanup(struct testsuite *ts) {
	if (ts->log && ts->log != stdout) {
		fclose(ts->log);
	}
}

void ts_print(struct testsuite *ts) {
	printf("Test results:\n");
	printf("  tests passed:      %d\n", ts->pass);
	printf("  tests failed:      %d\n", ts->fail);
	printf("  unexpected passes: %d\n", ts->xpass);
	printf("  expected failures: %d\n", ts->xfail);
	printf("  tests skipped:     %d\n", ts->skip);
	printf("  test errors:       %d\n", ts->error);
	printf("\n");
	printf("Total tests run:     %d\n", ts->total);
}

int ts_log_va(struct testsuite *ts, const char *test_name, const char *fmt, va_list ap) {
	int res = 0;

	if (!ts->single_test_mode) {
		res = fprintf(ts->log, "%s: ", test_name);
	}

	res += vfprintf(ts->log, fmt, ap);
	fflush(ts->log);
	return res;
}

int __attribute__((format(printf, 3, 4))) ts_log(struct testsuite *ts, const char *test_name, const char *fmt, ...) {
	va_list ap;
	int res;
	va_start(ap, fmt);
	res = ts_log_va(ts, test_name, fmt, ap);
	va_end(ap);
	return res;
}

enum ts_result ts_pass(struct testsuite *ts, const char *test_name) {
	ts->pass++;
	ts->total++;
	
	ts_log(ts, test_name, "test passed\n");
	return TS_PASS;
}

enum ts_result ts_fail(struct testsuite *ts, const char *test_name) {
	ts->fail++;
	ts->total++;
	
	ts_log(ts, test_name, "test failed\n");
	return TS_FAIL;
}

enum ts_result ts_xpass(struct testsuite *ts, const char *test_name) {
	ts->xpass++;
	ts->total++;

	ts_log(ts, test_name, "unexpected pass\n");
	return TS_XPASS;
}

enum ts_result ts_xfail(struct testsuite *ts, const char *test_name) {
	ts->xfail++;
	ts->total++;

	ts_log(ts, test_name, "expected failure\n");
	return TS_XFAIL;
}

enum ts_result ts_skip(struct testsuite *ts, const char *test_name) {
	ts->skip++;
	ts->total++;

	ts_log(ts, test_name, "test skipped\n");
	return TS_SKIP;
}

enum ts_result ts_error(struct testsuite *ts, const char *test_name) {
	ts->error++;
	ts->total++;

	ts_log(ts, test_name, "error running test\n");
	return TS_ERROR;
}

