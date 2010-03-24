--
-- Asterisk -- An open source telephony toolkit.
--
-- Copyright (C) 1999 - 2008, Digium, Inc.
--
-- Matthew Nicholson <mnicholson@digium.com>
--
-- See http://www.asterisk.org for more information about
-- the Asterisk project. Please do not directly contact
-- any of the maintainers of this project for assistance;
-- the project provides a web site, mailing lists and IRC
-- channels for your use.
--
-- This program is free software, distributed under the terms of
-- the GNU General Public License Version 2. See the LICENSE file
-- at the top of the source tree.
--

module(..., package.seeall)

-- 
-- replacements for global functions
--

-- print to the test log instead of stdout
function _G.print(...)
	local msg = ""
	for i=1,select('#', ...) do
		if i == 1 then
			msg = msg .. tostring(select(i, ...))
		else
			msg = msg .. "\t" .. tostring(select(i, ...))
		end
	end
	msg = msg .. "\n"
	log(msg)
end

_G.lua_error = _G.error
_G.xfail = xfail

--
-- basic pass/fail/skip/error functions
-- note: none of these functions actually return
--

function pass(reason)
	return lua_error{result = "pass", reason = reason}
end
_G.pass = pass

function fail(reason)
	return lua_error{result = "fail", reason = reason}
end
_G.fail = fail

function skip(reason)
	return lua_error{result = "skip", reason = reason}
end
_G.skip = skip

function error(reason)
	return lua_error{result = "error", reason = reason}
end
_G.error = error

--
-- utility functions
--

-- skip if the given condition is met
function skip_if(condition, message)
	if condition then
		return skip(message)
	end
end
_G.skip_if = skip_if

-- fail if the given condition is met
function fail_if(condition, message)
	if condition then
		return fail(message)
	end
end
_G.fail_if = fail_if

-- fail if condition is false using message as the reason
function check(condition, message)
	fail_if(not condition, message)
end
_G.check = check

