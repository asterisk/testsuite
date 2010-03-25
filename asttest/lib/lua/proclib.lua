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

function exec_and_wait(name, ...)
	p = exec(name, unpack(arg))
	return p:wait()
end

--- Send the term signal and give the process 10 seconds to exit then kill it.
-- @return whatever term() or kill() returned
function proc:term_or_kill()
	local res, err = self:term(10000)
	if not res and err == 'timeout' then
		return self:kill()
	end

	return res, err
end

