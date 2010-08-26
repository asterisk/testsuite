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

#include "astlib_lua.h"

#include <dirent.h>
#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <libgen.h>

/*!
 * \brief Make the parent directories of a given path.
 * \param pathname the path to create
 * \param mode the mode of the created directories
 *
 * Create the parent directories of a given path if they do not exist.  If the
 * given string does not end in '/' then the last path component will be
 * treated as a file name and ignored.
 *
 * \note In the case of an error, errno should be set.
 * \retval 0 success
 * \retval -1 error
 */
static int mkdir_p(const char *pathname, mode_t mode) {
	char buf[PATH_MAX + 1];
	const char *c = pathname;

	while ((c = strchr(c, '/'))) {
		c++;
		if (c - pathname > PATH_MAX) {
			errno = ENAMETOOLONG;
			goto e_return;
		}

		strncpy(buf, pathname, c - pathname);
		buf[c - pathname] = '\0';

		if (mkdir(buf, mode) && errno != EEXIST) {
			goto e_return;
		}
	}

	return 0;

e_return:
	return -1;
}

/*!
 * \brief Symlink a file.
 * \param L the lua state to use
 * \param src the source file
 * \param dst the destination file
 *
 * \retval 0 success
 * \retval -1 error
 */
static int symlink_file(lua_State *L, const char *src, const char *dst) {
	if (symlink(src, dst)) {
		lua_pushstring(L, "error symlink '");
		lua_pushstring(L, dst);
		lua_pushstring(L, "': ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 4);
		goto e_return;
	}
	return 0;

e_return:
	return -1;
}

/*!
 * \brief Recursively symlink and copy a directory.
 * \param L the lua state to use
 * \param src the source directory
 * \param dst the destination directory
 *
 * This function recursively creates symlinks to files in src in the dst
 * directory.  It does not symlink directories and instead makes new
 * directories in dst matching the corisponding dir in src.
 *
 * \note On error an error message is pushed onto the given lua stack.
 *
 * \retval 0 success
 * \retval -1 error
 */
static int symlink_copy_dir(lua_State *L, const char *src, const char *dst) {
	DIR *src_dir;
	struct dirent *d;
	char src_path[PATH_MAX], dst_path[PATH_MAX];
	struct stat st;

	if (!(src_dir = opendir(src))) {
		lua_pushstring(L, "error opening dir '");
		lua_pushstring(L, src);
		lua_pushstring(L, "': ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 4);
		goto e_return;
	}

	while ((d = readdir(src_dir))) {
		snprintf(src_path, sizeof(src_path), "%s/%s", src, d->d_name);
		snprintf(dst_path, sizeof(dst_path), "%s/%s", dst, d->d_name);

		if (!strcmp(d->d_name, ".") || !strcmp(d->d_name, "..")) {
			continue;
		}

		if (lstat(src_path, &st)) {
			lua_pushstring(L, "error with stat for '");
			lua_pushstring(L, src_path);
			lua_pushstring(L, "': ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			goto e_closedir;
		}

		if (S_ISDIR(st.st_mode)) {
			if (mkdir(dst_path, st.st_mode)) {
				lua_pushstring(L, "error creating dir '");
				lua_pushstring(L, dst_path);
				lua_pushstring(L, "': ");
				lua_pushstring(L, strerror(errno));
				lua_concat(L, 4);
				goto e_closedir;
			}

			if (symlink_copy_dir(L, src_path, dst_path)) {
				goto e_closedir;
			}
		} else if (S_ISREG(st.st_mode) || S_ISLNK(st.st_mode)) {
			if (symlink_file(L, src_path, dst_path)) {
				goto e_closedir;
			}
		} else {
			/* XXX we don't know what kind of file this is so we
			 * will ignore it silently, at some point in the future
			 * we should log this event somewhere */
			continue;
#if 0
			/* unsupported file type */
			lua_pushstring(L, "don't know how to symlink '");
			lua_pushstring(L, src_path);
			lua_pushstring(L, "' (unsupported file type)");
			lua_concat(L, 3);
			goto e_closedir;
#endif
		}
	}

	closedir(src_dir);
	return 0;

e_closedir:
	closedir(src_dir);
e_return:
	return -1;
}

/*!
 * \brief Recursively unlink a path.
 * \param L the lua state to use
 * \param path the file or directory to unlink
 *
 * This function unlinks the given file or directory.  If path is a directory,
 * all of the items in the directory will be recursively unlinked.
 *
 * \note On error an error message is pushed onto the given lua stack.
 *
 * \retval 0 success
 * \retval -1 error
 */
static int recursive_unlink(lua_State *L, const char *path) {
	DIR *dir;
	struct dirent *d;
	char dir_path[PATH_MAX];
	struct stat st;

	if (lstat(path, &st)) {
		if (errno == ENOENT)
			return 0;

		lua_pushstring(L, "error with stat for '");
		lua_pushstring(L, path);
		lua_pushstring(L, "': ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 4);
		return -1;
	}

	if (S_ISDIR(st.st_mode)) {
		if (!(dir = opendir(path))) {
			lua_pushstring(L, "error opening dir '");
			lua_pushstring(L, path);
			lua_pushstring(L, "': ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			return -1;
		}

		while ((d = readdir(dir))) {
			snprintf(dir_path, sizeof(dir_path), "%s/%s", path, d->d_name);

			if (!strcmp(d->d_name, ".") || !strcmp(d->d_name, "..")) {
				continue;
			}

			if (recursive_unlink(L, dir_path)) {
				closedir(dir);
				return -1;
			}
		}

		closedir(dir);
		rmdir(path);
	} else {
		if (unlink(path)) {
			lua_pushstring(L, "error unlinking path '");
			lua_pushstring(L, path);
			lua_pushstring(L, "': ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			return -1;
		}
	}

	return 0;
}

/*!
 * \brief [lua_CFunction asterisk:_new] Partially create an instance of the
 * asterisk object.
 * \param L the lua state to use
 *
 * This function creates and partially initilizes an instance of the asterisk
 * object.  It also increments the global asterisk instance index.
 *
 * \return new instance of the asterisk object
 */
static int new_asterisk(lua_State *L) {
	int asterisk_count;
	char path[PATH_MAX];
	char *bname;

	/* get the index for this instance */
	lua_getfield(L, LUA_REGISTRYINDEX, "astlib_count");
	asterisk_count = lua_tointeger(L, -1);

	/* increment the count */
	lua_pushinteger(L, asterisk_count + 1);
	lua_setfield(L, LUA_REGISTRYINDEX, "astlib_count");
	lua_pop(L, 1);

	/* create a new table and set some initial values */
	lua_newtable(L);

	if (!getcwd(path, sizeof(path))) {
		lua_pushliteral(L, "error determining working directory: ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		return lua_error(L);
	}

	bname = basename(path);
	/* handle some special basename paths by putting the tmp dir in the
	 * current directory, otherwise put it in /tmp */
	if (!strcmp(bname, ".") || !strcmp(bname, "..") || !strcmp(bname, "/")) {
		lua_pushstring(L, getcwd(path, sizeof(path)));
		lua_pushliteral(L, "/tmp/ast");
		lua_pushinteger(L, asterisk_count);
		lua_concat(L, 3);
		lua_setfield(L, -2, "work_area");
	} else {
		lua_pushliteral(L, "/tmp/asterisk-testsuite/");
		lua_pushstring(L, bname);
		lua_pushliteral(L, "/ast");
		lua_pushinteger(L, asterisk_count);
		lua_concat(L, 4);
		lua_setfield(L, -2, "work_area");
	}

	lua_pushinteger(L, asterisk_count);
	lua_setfield(L, -2, "index");

	lua_getfield(L, LUA_REGISTRYINDEX, "astlib_path");
	lua_pushliteral(L, "/usr/sbin/asterisk");
	lua_concat(L, 2);
	lua_setfield(L, -2, "asterisk_binary");
	return 1;
}

/*!
 * \brief [lua_CFunction asterisk:_version] get the version of this asterisk instance
 * \return the version string for this version of asterisk
 */
static int get_asterisk_version(lua_State *L) {
	lua_getfield(L, LUA_REGISTRYINDEX, "astlib_version");
	return 1;
}

/*!
 * \brief [lua_CFunction asterisk:clean_work_area] Clean up the work area for
 * this instance.
 * \param L the lua state to use
 *
 * This function cleans up the work area for this instance by deleting the work
 * area directory if it exists.
 */
static int clean_work_area(lua_State *L) {
	const char *work_area;
	luaL_checktype(L, 1, LUA_TTABLE);

	/* get the work area for this instance */
	lua_getfield(L, 1, "work_area");
	work_area = lua_tostring(L, -1);

	if (recursive_unlink(L, work_area)) {
		lua_pushstring(L, "\nerror cleaning work area");
		lua_concat(L, 2);
		return lua_error(L);
	}

	return 0;
}

/*!
 * \brief [lua_CFunction asterisk:create_work_area] Create the work area.
 * \param L the lua state to use
 *
 * This function copies and symlinks files from the asterisk path to prepare
 * the work area for this instance.
 */
static int create_work_area(lua_State *L) {
	const char *work_area;
	const char *asterisk_path;
	char src_buf[PATH_MAX], dst_buf[PATH_MAX];
	mode_t dir_mode = S_IRWXU | S_IRGRP| S_IXGRP| S_IROTH | S_IXOTH;
	int i;

	/* directories must end in '/' */
	const char *copy_dirs[] = {
		"/etc/asterisk/",
		"/usr/lib/asterisk/modules/",
		"/usr/include/asterisk/",
		"/var/lib/asterisk/",
		"/var/log/asterisk/",
		"/var/spool/asterisk/",
		NULL,
	};

	/* directories must end in '/' */
	const char *create_dirs[] = {
		"/var/run/asterisk/",
		NULL,
	};

	const char *asterisk_files[] = {
		"/usr/sbin/astcanary",
		"/usr/sbin/asterisk",
		"/usr/sbin/astgenkey",
		"/usr/sbin/autosupport",
		"/usr/sbin/rasterisk",
		"/usr/sbin/safe_asterisk",
		NULL,
	};

	luaL_checktype(L, 1, LUA_TTABLE);

	/* get the work area for this instance */
	lua_getfield(L, 1, "work_area");
	work_area = lua_tostring(L, -1);

	/* get the asterisk path */
	lua_getfield(L, LUA_REGISTRYINDEX, "astlib_path");
	asterisk_path = lua_tostring(L, -1);

	/* copy directories */
	for (i = 0; copy_dirs[i]; i++) {
		snprintf(src_buf, sizeof(src_buf), "%s%s", asterisk_path, copy_dirs[i]);
		snprintf(dst_buf, sizeof(dst_buf), "%s%s", work_area, copy_dirs[i]);
		if (mkdir_p(dst_buf, dir_mode)) {
			lua_pushstring(L, "unable to create directory in work area (");
			lua_pushstring(L, dst_buf);
			lua_pushstring(L, "): ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			return lua_error(L);
		}

		if (symlink_copy_dir(L, src_buf, dst_buf)) {
			lua_pushstring(L, "\nerror initilizing work area");
			lua_concat(L, 2);
			return lua_error(L);
		}
	}

	/* create directories */
	for (i = 0; create_dirs[i]; i++) {
		snprintf(src_buf, sizeof(src_buf), "%s%s", asterisk_path, create_dirs[i]);
		snprintf(dst_buf, sizeof(dst_buf), "%s%s", work_area, create_dirs[i]);
		if (mkdir_p(dst_buf, dir_mode)) {
			lua_pushstring(L, "unable to create directory in work area (");
			lua_pushstring(L, dst_buf);
			lua_pushstring(L, "): ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			return lua_error(L);
		}
	}

	/* copy files */
	for (i = 0; asterisk_files[i]; i++) {
		snprintf(src_buf, sizeof(src_buf), "%s%s", asterisk_path, asterisk_files[i]);
		snprintf(dst_buf, sizeof(dst_buf), "%s%s", work_area, asterisk_files[i]);
		if (mkdir_p(dst_buf, dir_mode)) {
			lua_pushstring(L, "unable to create directory in work area (");
			lua_pushstring(L, dst_buf);
			lua_pushstring(L, "): ");
			lua_pushstring(L, strerror(errno));
			lua_concat(L, 4);
			return lua_error(L);
		}

		if (symlink_file(L, src_buf, dst_buf)) {
			lua_pushstring(L, "\nerror initilizing work area");
			lua_concat(L, 2);
			return lua_error(L);
		}
	}
	return 0;
}

/*!
 * \brief [lua_CFunction ast.unlink] Unlink the given file.
 * \param L the lua state to use
 *
 * \retval -1 error
 * \retval 0 success
 */
static int unlink_file(lua_State *L) {
	const char *file = luaL_checkstring(L, 1);
	lua_pushinteger(L, unlink(file));
	return 1;
}

static int set_gc_func(lua_State *L) {
	lua_pushvalue(L, 1);
	lua_setfield(L, LUA_REGISTRYINDEX, "astlib_asterisk_gc");
	return 0;
}

static int setup_gc(lua_State *L) {
	/* since we know this function is only called by internal methods, we
	 * don't do any error checking
	 *
	 * We expect two arguments, an asterisk table and a proc table */

	/* create a special userdata so that we can have a __gc method called
	 * on our proc table */
	lua_pushvalue(L, 2);
	lua_replace(L, LUA_ENVIRONINDEX);

	lua_pushliteral(L, "__gc");

	lua_newuserdata(L, sizeof(char));

	/* create the metatable for our special userdata */
	lua_createtable(L, 0, 1);

	/* call our __gc closure generator and store the result */
	lua_getfield(L, LUA_REGISTRYINDEX, "astlib_asterisk_gc");
	lua_pushvalue(L, 1);
	lua_pushvalue(L, 2);
	lua_call(L, 2, 1);
	lua_setfield(L, -2, "__gc");

	lua_setmetatable(L, -2);

	/* store the new userdata in the proc table */
	lua_settable(L, 2);
	return 0;
}

static luaL_Reg astlib[] = {
	{"unlink", unlink_file},
	{"_version", get_asterisk_version},
	{"_set_asterisk_gc_generator", set_gc_func},
	{"_setup_gc", setup_gc},
	{NULL, NULL},
};

static luaL_Reg asterisk_table[] = {
	{"_new", new_asterisk},
	{"clean_work_area", clean_work_area},
	{"create_work_area", create_work_area},
	{NULL, NULL},
};

int luaopen_astlib(lua_State *L) {
	const char *asterisk_path = luaL_checkstring(L, 1);
	const char *asterisk_version = luaL_optstring(L, 2, "unknown");

	/* set up some registry values */
	lua_pushstring(L, asterisk_path);
	lua_setfield(L, LUA_REGISTRYINDEX, "astlib_path");

	lua_pushstring(L, asterisk_version);
	lua_setfield(L, LUA_REGISTRYINDEX, "astlib_version");

	lua_pushinteger(L, 1);
	lua_setfield(L, LUA_REGISTRYINDEX, "astlib_count");

	/* register our functions */
	luaL_register(L, "ast", astlib);

	/* set up the 'path' variable */
	lua_pushstring(L, asterisk_path);
	lua_setfield(L, -2, "path");

	/* set up the 'asterisk' table and add some functions to it */
	lua_newtable(L);
	luaL_register(L, NULL, asterisk_table);
	lua_setfield(L, -2, "asterisk");

	lua_pop(L, 1);
	
	/* load the lua portion of the lib */
	if (luaL_loadbuffer(L, astlib_lua, sizeof(astlib_lua), "astlib"))
		goto e_lua_error;
	lua_pushstring(L, "ast");
	if (lua_pcall(L, 1, 1, 0))
		goto e_lua_error;

	return 1;

e_lua_error:
	/* format the error message a little */
	lua_pushstring(L, "error loading ast library: ");
	lua_insert(L, -2);
	lua_concat(L, 2);
	return lua_error(L);
}

