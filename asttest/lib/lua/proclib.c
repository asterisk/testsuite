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

#include "proclib_lua.h"

#include <errno.h>
#include <signal.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/time.h>
#include <time.h>


/*!
 * \brief Check if we can execute the given file.
 * \warn This function only does a very basic check of executability.  It is
 * possible for this function to say a file is executable, but the file not
 * actually be executable by the user under the current circumstances.
 */
static int is_executable(lua_State *L) {
	struct stat st;
	const char *path = luaL_checkstring(L, 1);

	if (stat(path, &st)) {
		lua_pushboolean(L, 0);
		lua_pushstring(L, strerror(errno));
		return 2;
	}

	if (!S_ISREG(st.st_mode)) {
		lua_pushboolean(L, 0);
		lua_pushliteral(L, "path is not a regular file");
		return 2;
	}

	if (!((S_IXUSR | S_IXGRP | S_IXOTH) & st.st_mode)) {
		lua_pushboolean(L, 0);
		lua_pushliteral(L, "path is not executable");
		return 2;
	}

	/* the file might be executable */
	lua_pushboolean(L, 1);
	return 1;
}

/*!
 * \brief [lua_CFunction proc.exists] Check if the given file exists and is
 * executable.
 * \param L the lua state to use
 */
static int proc_exists(lua_State *L) {
	char *env_path;
	const char *path = luaL_checkstring(L, 1);
	char *p;
	char *c;

	if (strlen(path) == 0) {
		lua_pushboolean(L, 0);
		lua_pushliteral(L, "invalid path provided (path was an empty string)");
		return 2;
	}

	/* if path starts with '/' then directly stat the given path */
	if (path[0] == '/') {
		lua_pushcfunction(L, is_executable);
		lua_pushvalue(L, 1);
		lua_call(L, 1, 2);
		return 2;
	}

	if (!(env_path = getenv("PATH"))) {
		/* default env_path to the following as indicated in the
		 * exec(3) man page */
		env_path = ":/bin:/usr/bin";
	}

	p = env_path;
	for (p = env_path; (c = strchr(p, ':')); p = ++c) {
		if (c - p <= 1) {
			/* empty path component */
			continue;
		}

		lua_pushcfunction(L, is_executable);

		lua_pushlstring(L, p, c - p);
		lua_pushliteral(L, "/");
		lua_pushvalue(L, 1);
		lua_concat(L, 3);

		lua_call(L, 1, 2);

		if (lua_toboolean(L, -2)) {
			lua_pop(L, 1);
			return 1;
		}

		lua_pop(L, 2);
	}

	/* check the last path component */
	if (strlen(p) != 0) {
		lua_pushcfunction(L, is_executable);

		lua_pushstring(L, p);
		lua_pushliteral(L, "/");
		lua_pushvalue(L, 1);
		lua_concat(L, 3);

		lua_call(L, 1, 2);

		if (lua_toboolean(L, -2)) {
			lua_pop(L, 1);
			return 1;
		}

		lua_pop(L, 2);
	}

	/* no executable paths were found */
	lua_pushboolean(L, 0);
	lua_pushliteral(L, "no executable found for path '");
	lua_pushvalue(L, 1);
	lua_pushliteral(L, "'");
	lua_concat(L, 3);
	return 2;
}

static FILE *create_iolib_file(lua_State *L, const char *name, int fd, const char *mode) {
	FILE **file;

	lua_pushstring(L, name);
	file = lua_newuserdata(L, sizeof(FILE *));
	*file = fdopen(fd, mode);
	luaL_getmetatable(L, LUA_FILEHANDLE);
	lua_setmetatable(L, -2);
	lua_rawset(L, -3);
	return *file;
}

/*!
 * \brief Create and array with the function arguments suitable to pass to
 * execvp.
 * \param L the lua state to use
 */
static const char **build_argv(lua_State *L, const char *name) {
	int args = lua_gettop(L);
	const char **argv;
	size_t argc;
	int i;

	argc = args + 1; /* the number of args plus 1 for the terminating NULL */
	if (!(argv = malloc(argc * sizeof(char *)))) {
		lua_pushliteral(L, "error allocating memory while spawning process");
		lua_error(L); /* never returns */
	}

	argv[0] = name;
	argv[args] = NULL;

	for (i = 2; i <= args; i++) {
		argv[i - 1] = lua_tostring(L, i);
	}

	return argv;
}

/*!
 * \brief [lua_CFunction proc.exec_io] Start a process.
 * \param L the lua state to use
 *
 * This function forks and execs the given process with support for reading
 * from and writing to stdio file descriptors.
 */
static int exec_proc_with_stdio(lua_State *L) {
	pid_t pid;
	pid_t *p;
	const char *name = luaL_checkstring(L, 1);
	const char **argv = build_argv(L, name);
	int stdin_pipe[2], stdout_pipe[2], stderr_pipe[2];

	/* make sure the given path exists and is executable */
	lua_pushcfunction(L, proc_exists);
	lua_pushvalue(L, 1);
	lua_call(L, 1, 2);

	if (!lua_toboolean(L, -2)) {
		goto e_return;
	}

	if (pipe(stdin_pipe)) {
		lua_pushliteral(L, "error creating stdin pipe: ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		goto e_free_argv;
	}

	if (pipe(stdout_pipe)) {
		lua_pushliteral(L, "error creating stdout pipe: ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		goto e_close_stdin_pipe;
	}

	if (pipe(stderr_pipe)) {
		lua_pushliteral(L, "error creating stderr pipe: ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		goto e_close_stdout_pipe;
	}

	/* start the process */
	pid = fork();
	if (pid == 0) {
		/* replace stdin, stdout, and stderr with our pipes */
		dup2(stdin_pipe[0], STDIN_FILENO);
		dup2(stdout_pipe[1], STDOUT_FILENO);
		dup2(stderr_pipe[1], STDERR_FILENO);

		/* close the halves of the pipes that we don't need */
		close(stdin_pipe[1]);
		close(stdout_pipe[0]);
		close(stderr_pipe[0]);

		execvp(name, (char * const *) argv);
		fprintf(stderr, "error spawning process: %s\n", strerror(errno));
		exit(1);
	} else if (pid == -1) {
		lua_pushliteral(L, "error spawning process (fork error): ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		goto e_close_stderr_pipe;
	}

	free(argv);

	/* close the halves of the pipes that we don't need */
	close(stdin_pipe[0]);
	close(stdout_pipe[1]);
	close(stderr_pipe[1]);

	lua_newtable(L);
	luaL_getmetatable(L, "proclib_proc");
	lua_setmetatable(L, -2);

	/* now create lua FILE* objects from our file descriptors */
	create_iolib_file(L, "stdin", stdin_pipe[1], "w");
	create_iolib_file(L, "stdout", stdout_pipe[0], "r");
	create_iolib_file(L, "stderr", stderr_pipe[0], "r");


	/* store the pid */
	lua_pushliteral(L, "pid");
	p = lua_newuserdata(L, sizeof(pid_t));
	*p = pid;
	luaL_getmetatable(L, "proclib_pid");
	lua_setmetatable(L, -2);
	lua_rawset(L, -3);

	return 1;

e_close_stderr_pipe:
	close(stderr_pipe[0]);
	close(stderr_pipe[1]);

e_close_stdout_pipe:
	close(stdout_pipe[0]);
	close(stdout_pipe[1]);

e_close_stdin_pipe:
	close(stdin_pipe[0]);
	close(stdin_pipe[1]);

e_free_argv:
	free(argv);

e_return:
	/* error string should already be on the stack */
	return lua_error(L);
}

/*!
 * \brief [lua_CFunction proc.exec] Start a process.
 * \param L the lua state to use
 *
 * This function forks and execs the given process.
 */
static int exec_proc(lua_State *L) {
	pid_t pid;
	pid_t *p;
	const char *name = luaL_checkstring(L, 1);
	const char **argv = build_argv(L, name);
	int fd;

	/* make sure the given path exists and is executable */
	lua_pushcfunction(L, proc_exists);
	lua_pushvalue(L, 1);
	lua_call(L, 1, 2);

	if (!lua_toboolean(L, -2)) {
		goto e_return;
	}

	/* start the process */
	pid = fork();
	if (pid == 0) {
		/* open dev null and use it for stdin, stdout, and stderr */
		fd = open("/dev/null", O_RDWR);
		/* XXX check for error?!! */
		dup2(fd, STDIN_FILENO);
		dup2(fd, STDOUT_FILENO);
		dup2(fd, STDERR_FILENO);

		execvp(name, (char * const *) argv);
		exit(1);
	} else if (pid == -1) {
		lua_pushliteral(L, "error spawning process (fork error): ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		goto e_free_argv;
	}

	free(argv);

	lua_newtable(L);
	luaL_getmetatable(L, "proclib_proc");
	lua_setmetatable(L, -2);

	/* store the pid */
	lua_pushliteral(L, "pid");
	p = lua_newuserdata(L, sizeof(pid_t));
	*p = pid;
	luaL_getmetatable(L, "proclib_pid");
	lua_setmetatable(L, -2);
	lua_rawset(L, -3);

	return 1;

e_free_argv:
	free(argv);

e_return:
	/* error string should already be on the stack */
	return lua_error(L);
}
/*!
 * \brief [lua_CFunction pid:__gc] Kill the process with the given pid.
 * \param L the lua state to use
 *
 * This is the gc function for the pid userdata.  This function will send a
 * TERM signal to the process and then run waitpid.  If the process has not
 * exited after about 1.5 seconds, SIGKILL will be sent.
 */
static int pid_gc(lua_State *L) {
	int i = 0;
	pid_t *p = luaL_checkudata(L, 1, "proclib_pid");
	if (kill(*p, SIGTERM)) {
		return 0;
	}

	/* wait for the process to exit, after about 1.5 seconds, send SIGKILL */
	while (waitpid(*p, NULL, WNOHANG) == 0) {
		if (++i == 3) {
			kill(*p, SIGKILL);
			continue;
		}
		usleep(500);
	}

	return 0;
}

/*!
 * \brief Convert a timeval struct to milliseconds.
 * \param tv the timeval struct to operate on
 * \return the value of the given timeval expressed in milliseconds
 */
static long tv2ms(struct timeval *tv) {
	return (tv->tv_sec * 1000 + tv->tv_usec / 1000);
}

/*!
 * \brief [lua_CFunction proc:wait] Wait for the process to end.
 * \param L the lua state to use
 * \param timeout an optional timeout in milliseconds
 *
 * This function calls waitpid on the running process.
 *
 * \return a tuple containg the exit code, nil and the signal that caused the
 * process to exit, or nil and a string describing the error ("error",
 * "timeout", or "core" currently).
 */
static int wait_proc(lua_State *L) {
	pid_t pid;
	int status;
	int res;
	long timeout = luaL_optlong(L, 2, -1);
	long start;
	struct timeval tv;

	luaL_checktype(L, 1, LUA_TTABLE);

	if (gettimeofday(&tv, NULL)) {
		lua_pushliteral(L, "error running gettimeofday() for timeout calculations: ");
		lua_pushstring(L, strerror(errno));
		lua_concat(L, 2);
		return lua_error(L);
	}
	start = tv2ms(&tv);

	/* get the pid of this process */
	lua_getfield(L, 1, "pid");
	if (lua_isnil(L, -1)) {
		/* no process found */
		lua_pushnil(L);
		lua_pushliteral(L, "error");
		return 2;
	}
	pid = *(pid_t *) lua_touserdata(L, -1);
	lua_pop(L, 1);

	if (timeout >= 0) {
		while ((res = waitpid(pid, &status, WNOHANG)) == 0) {
			/* check the timeout */
			if (gettimeofday(&tv, NULL)) {
				lua_pushliteral(L, "error running gettimeofday() for timeout calculations: ");
				lua_pushstring(L, strerror(errno));
				lua_concat(L, 2);
				return lua_error(L);
			}

			if (timeout < tv2ms(&tv) - start) {
				lua_pushnil(L);
				lua_pushliteral(L, "timeout");
				return 2;
			}
			usleep(1);
		}

		if (res == -1) {
			/* waitpid failed */
			lua_pushnil(L);
			lua_pushliteral(L, "error");
			return 2;
		}
	} else {
		if (waitpid(pid, &status, 0) == -1) {
			/* waitpid failed */
			lua_pushnil(L);
			lua_pushliteral(L, "error");
			return 2;
		}
	}

	if (WIFEXITED(status)) {
		lua_pushinteger(L, WEXITSTATUS(status));
		lua_pushnil(L);
	} else if (WIFSIGNALED(status)) {
		lua_pushnil(L);
		if (WCOREDUMP(status))
			lua_pushliteral(L, "core");
		else
			lua_pushinteger(L, WTERMSIG(status));
	} else {
		lua_pushliteral(L, "unknown error running waitpid");
		return lua_error(L);
	}

	/* unset the pid */
	lua_pushliteral(L, "pid");
	lua_pushnil(L);
	lua_rawset(L, 1);

	return 2;
}

/*!
 * \brief [lua_CFunction proc:kill] Kill the process with SIGKILL.
 * \param L the lua state to use
 *
 * This function sends SIGKILL then calls proc:wait() and returns the
 * result.
 *
 * \return same as wait_proc() and in the case of "error" an additional error
 * description and errno may be returned
 */
static int kill_proc(lua_State *L) {
	pid_t pid;

	luaL_checktype(L, 1, LUA_TTABLE);

	/* get the pid of this process */
	lua_getfield(L, 1, "pid");
	if (lua_isnil(L, -1)) {
		/* no process found */
		lua_pushnil(L);
		lua_pushliteral(L, "error");
		return 2;
	}
	pid = *(pid_t *) lua_touserdata(L, -1);
	lua_pop(L, 1);

	if (kill(pid, SIGKILL)) {
		lua_pushnil(L);
		lua_pushliteral(L, "error");
		lua_pushstring(L, strerror(errno));
		lua_pushinteger(L, errno);
		return 4;
	}

	lua_pushcfunction(L, wait_proc);
	lua_pushvalue(L, 1);
	lua_call(L, 1, 2);
	return 2;
}

/*!
 * \brief [lua_CFunction proc:term] Terminate process with SIGTERM.
 * \param L the lua state to use
 * \param timeout an optional timeout in milliseconds that will be passed to proc:wait()
 *
 * This function sends SIGTERM then calls proc:wait() and returns the result.
 *
 * \return same as wait_proc() and in the case of "error" an additional error
 * description and errno may be returned
 */
static int terminate_proc(lua_State *L) {
	pid_t pid;
	long timeout = luaL_optlong(L, 2, -1);

	luaL_checktype(L, 1, LUA_TTABLE);

	/* get the pid of this process */
	lua_getfield(L, 1, "pid");
	if (lua_isnil(L, -1)) {
		/* no process found */
		lua_pushnil(L);
		lua_pushliteral(L, "error");
		return 2;
	}
	pid = *(pid_t *) lua_touserdata(L, -1);
	lua_pop(L, 1);

	if (kill(pid, SIGTERM)) {
		lua_pushnil(L);
		lua_pushliteral(L, "error");
		lua_pushstring(L, strerror(errno));
		lua_pushinteger(L, errno);
		return 4;
	}

	lua_pushcfunction(L, wait_proc);
	lua_pushvalue(L, 1);
	if (timeout == -1) {
		lua_pushnil(L);
	} else {
		lua_pushvalue(L, 2);
	}

	lua_call(L, 2, 2);
	return 2;
}

static luaL_Reg proclib[] = {
	{"exists", proc_exists},
	{"exec", exec_proc},
	{"exec_io", exec_proc_with_stdio},
	{NULL, NULL},
};

static luaL_Reg proc_pid[] = {
	{"__gc", pid_gc},
	{NULL, NULL},
};

static luaL_Reg proc_table[] = {
	{"wait", wait_proc},
	{"term", terminate_proc},
	{"kill", kill_proc},
	{NULL, NULL},
};

/* copied from liolib.c in the lua source */
static int pushresult (lua_State *L, int i, const char *filename) {
	int en = errno;  /* calls to Lua API may change this value */
	if (i) {
		lua_pushboolean(L, 1);
		return 1;
	} else {
		lua_pushnil(L);
		if (filename)
			lua_pushfstring(L, "%s: %s", filename, strerror(en));
		else
			lua_pushfstring(L, "%s", strerror(en));
		lua_pushinteger(L, en);
		return 3;
	}
}

/* adapted from io_fclose in liolib.c in the lua source */
static int io_fclose (lua_State *L) {
	FILE **p = luaL_checkudata(L, 1, LUA_FILEHANDLE);
	int ok = (fclose(*p) == 0);
	*p = NULL;
	return pushresult(L, ok, NULL);
}

int luaopen_proclib(lua_State *L) {
	/* set up a private environment containing a __close function that is
	 * necessary for using the LUA_FILEHANDLE metatable.  This metatable is
	 * used by the proc.exec_io function to manage pipes for stdio.
	 */
	lua_createtable(L, 0, 1);
	lua_replace(L, LUA_ENVIRONINDEX);
	lua_pushcfunction(L, io_fclose);
	lua_setfield(L, LUA_ENVIRONINDEX, "__close");

	/* register our functions */
	luaL_register(L, "proc", proclib);

	/* set up the pid metatable */
	luaL_newmetatable(L, "proclib_pid");
	luaL_register(L, NULL, proc_pid);
	lua_pop(L, 1);

	/* set up the 'proc' metatable */
	luaL_newmetatable(L, "proclib_proc");

	/* set the __index value to itself */
	lua_pushstring(L, "__index");
	lua_pushvalue(L, -2);
	lua_settable(L, -3);

	luaL_register(L, NULL, proc_table);
	/* store this table as 'proc.proc' as well */
	lua_setfield(L, -2, "proc");

	lua_pop(L, 1);

	/* load the lua portion of the lib */
	if (luaL_loadbuffer(L, proclib_lua, sizeof(proclib_lua), "proclib"))
		goto e_lua_error;
	lua_pushstring(L, "proc");
	if (lua_pcall(L, 1, 1, 0))
		goto e_lua_error;

	return 1;

e_lua_error:
	/* format the error message a little */
	lua_pushstring(L, "error loading the proc library: ");
	lua_insert(L, -2);
	lua_concat(L, 2);
	return lua_error(L);
}

