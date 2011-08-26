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

#include <stdio.h>
#include <string.h>
#include <unistd.h>

#include "asttest/asttest.h"
#include "asttest/testutils.h"

const char *default_log_filename = "asttest.log";


void usage(const char *prog_name) {
	fprintf(stderr,
		"Usage:\n"
		"  %s [-wh] [-v <version>] [-l <filename>] [-a <directory>] <test_dir> [test_dir...]\n"
		"  %s [-wh] [-v <version>] [-l <filename>] [-a <directory>] -s <test_dir>\n"
		"\n"
		"Options:\n"
		"  -l <filename>  Specify the name of the log file.  One log file will be\n"
		"                 created for each test directory in that test directory\n"
		"                 using the given name.  The default filename is\n"
		"                 asttest.log.\n"
		"  -a <directory> Specify the directory asterisk has been installed in.\n"
		"                 This option is roughly equivalent to the value of\n"
		"                 --prefix at configure time.  The actually asterisk binary\n"
		"                 is expected to be located at <directory>/sbin/asterisk.\n"
		"                 The default is 'asterisk'.\n"
		"  -w             warn if tests were skipped because of errors.  This\n"
		"                 option will cause a warning to print instead of an\n"
		"                 error being generated if any tests fail because of\n"
		"                 errors.  This is ignored in single test mode.\n"
		"  -h             print this help message\n"
		"  -s <directory> Run in single test mode.  The given directory should contain a\n"
		"                 test.lua test script.  Single test mode will also cause test\n"
		"                 output to be sent to stdout instead of a log file and will\n"
		"                 cause the program to exit with a non zero return code in if\n"
		"                 the test fails.\n"
		"  -v <version>   Specify the version of asterisk we are testing against.  If\n"
		"                 not specified, the version.h file from the specified asterisk\n"
		"                 path will be usedi to determine the version number.\n"
		"\n"
		, prog_name, prog_name);
}

/*
 * \brief Parse command line options.
 * @param argc the argument count
 * @param argv an array of strings
 * @param opts the struct where our options will be stored
 * 
 * @note If this function returns 0 the remaining options should be test 
 * directories.
 *
 * @retval 1 -h option
 * @retval -1 error
 * @return 0 success
 */
int parse_cmdline(int argc, char *argv[], struct asttest_opts *opts) {
	char c;
	memset(opts, 0, sizeof(struct asttest_opts));

	/* set some default options */
	opts->warn_on_error = 0;
	opts->log_filename = default_log_filename;
	opts->asterisk_path = "asterisk";

	/* parse options */
	while ((c = getopt(argc, argv, "l:a:s:v:n:wh")) != -1) {
		switch (c) {
		case 'l':
			opts->log_filename = optarg;
			break;
		case 'w':
			opts->warn_on_error = 1;
			break;
		case 'a':
			opts->asterisk_path = optarg;
			break;
		case 's':
			opts->single_test_mode = optarg;
			break;
		case 'v':
			opts->asterisk_version = optarg;
			break;
		case 'h':
			return 1;
		case '?':
			return -1;
			break;
		}
	}

	return 0;
}

int main(int argc, char *argv[]) {
	int res = 0;
	int i;
	struct asttest_opts opts;

	if ((res = parse_cmdline(argc, argv, &opts))) {
		usage(argv[0]);

		if (res == 1)
			return 0;
		else
			return 1;
	}

	if (opts.single_test_mode) {
		return process_single_test(&opts);
	} else {
		if (optind == argc) {
			fprintf(stderr, "%s: missing arguments -- specify at least one test directory\n", argv[0]);
			usage(argv[0]);
			return 1;
		}

		for (i = optind; i < argc; i++) {
			if (process_test_dir(argv[i], &opts)) {
				fprintf(stderr, "test suite failed, exiting...\n");
				return 1;
			}
		}
	}

	return 0;
}
