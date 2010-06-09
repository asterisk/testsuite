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

#ifndef ASTTEST_ASTTEST_H
#define ASTTEST_ASTTEST_H

#include <linux/limits.h>

struct asttest_opts {
	unsigned int warn_on_error:1;
	const char *log_filename;
	const char *asterisk_path;
	const char *asterisk_version;
	const char *single_test_mode;
};

extern const char *default_log_filename;

#endif
