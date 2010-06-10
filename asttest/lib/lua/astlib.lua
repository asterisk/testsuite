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

function exists()
	return select(1, proc.exists(path .. "/usr/sbin/asterisk"))
end

function new()
	return asterisk:new()
end

function version(ver)
	local version = ver or _version()
	if version == "unknown" then
		-- read version from path .. /usr/include/asterisk/version.h
		local f, err = io.open(path .. "/usr/include/asterisk/version.h")
		if not f then
			error("error determining asterisk verison; unable to open version.h: " .. err)
		end

		for line in f:lines() do
			version = line:match('ASTERISK_VERSION%s"([^"]+)"')
			if version then
				break
			end
		end
		f:close()

		if not version then
			error("error determining asterisk version; version not found in version.h")
		end
	end
	return asterisk_version:new(version)
end

function has_major_version(v)
	if v == "trunk" then
		v = "SVN-trunk-r00000"
	end

	local v1 = version(v)
	local v2 = version()

	if v1.svn and v2.svn and v1.branch == v2.branch then return true end
	if v2.svn then
		v1 = version("SVN-branch-" .. v .. "-r00000")
		if v1.branch == v2.branch then return true end
	end
	if not v2.svn and not v1.svn and v1.concept == v2.concept and v1.major == v2.major then
		if not v1.minor then return true end
		if v1.minor == v2.minor then return true end
	end

	return false
end

-- asterisk table is created in astlib.c
function asterisk:new()
	local a = self:_new()
	a.configs = {}
	a.asterisk_conf = a.work_area .. "/etc/asterisk/asterisk.conf"
	a.essential_configs = {
		["asterisk.conf"] = asterisk.generate_asterisk_conf,
		["logger.conf"] = asterisk.generate_logger_conf,
	}

	setmetatable(a, self)
	return a
end

function asterisk:path(path)
	return self.work_area .. path
end

function asterisk:_spawn()
	local p = proc.exec(self.asterisk_binary,
		"-f", "-g", "-q", "-m",
		"-C", self.asterisk_conf
	)
	rawset(self, "proc", p)
end

-- note this timesout after five minutes
function asterisk:cli(command)
	local p = proc.exec_io(self.asterisk_binary,
		"-r", "-x", command,
		"-C", self.asterisk_conf
	)

	-- wait up to 5 minutes for the process to exit.  If the process does
	-- not exit within 5 minutes, return a error.
	local res, err = p:wait(300000)
	if not res then
		return res, err
	end

	return p.stdout:read("*a")
end

function asterisk:spawn()
	self:clean_work_area()
	self:create_work_area()
	self:generate_essential_configs()
	self:write_configs()
	self:_spawn()

	-- wait for asterisk to be fully booted.  We do this by reading the
	-- output of the 'core waitfullybooted' command and looking for the
	-- string 'fully booted'.  We will try 5 times before completely giving
	-- up with a one second delay in between each try.  We need to loop
	-- like this in order to give asterisk time to start the CLI socket.
	local booted
	for _=1,5 do
		local err
		booted, err = self:cli("core waitfullybooted")
		if not booted then
			if err then
				error("error waiting for asterisk to fully boot: " .. err)
			else
				error("error waiting for asterisk to fully boot")
			end
		end
		if booted:find("fully booted") then
			break
		end
		posix.sleep(1)
	end
	if not booted:find("fully booted") then
		print("error waiting for asterisk to fully boot: " .. booted)
		print("\nfull log follows:\n")
		self:dump_full_log()
		
		print("checking to see if asterisk is still running")
		local res, err = proc.perror(self:wait(1000))
		if not res and err == "timeout" then
			print("seems like asterisk is still running, but we cannot wait for it to be fully booted.  That is odd.")
		end

		error("error starting asterisk")
	end
end

function asterisk:spawn_and_wait()
	self:spawn()
	return self:wait()
end

function asterisk:wait(timeout)
	if not proc then return nil, "error" end
	return self.proc:wait(timeout)
end

function asterisk:term(timeout)
	if not proc then return nil, "error" end
	return self.proc:term(timeout)
end

function asterisk:kill()
	if not proc then return nil, "error" end
	return self.proc:kill()
end

function asterisk:term_or_kill()
	if not proc then return nil, "error" end
	return self.proc:term_or_kill()
end

function asterisk:__newindex(conffile_name, conffile)
	if (getmetatable(conffile) ~= config) then
		error("got " .. type(conffile) .. " expected type config")
	end
	self.configs[conffile_name] = conffile
	if conffile.name == "asterisk.conf" then
		self.asterisk_conf = conffile.filename
	end
end

--- Index an asterisk object
-- This function will return either the config with the given name, the actual
-- table member with the given name, or if neither of those exist, it will
-- create a config with the given name.
function asterisk:__index(key)
	if self.configs[key] then
		return self.configs[key]
	end

	if asterisk[key] ~= nil then
		return asterisk[key]
	end

	return self:new_config(key)
end

function asterisk:manager_connect()
	local m = manager:new()

	local res, err = m:connect("localhost", self.configs["manager.conf"]["general"].port)
	if not res then
		return nil, err
	end

	return m
end

function asterisk:load_config(file, conf_name)
	-- if conf_name is not specified, pull it from the string
	if not conf_name then
		if file:find("/") then
			conf_name = file:match(".*/(.+)$")
		else
			conf_name = file
		end
	end

	local c = config:from_file(conf_name, file, self:path("/etc/asterisk/") .. conf_name)
	self[conf_name] = c
	return c
end

function asterisk:new_config(name)
	local c = config:new(name, self:path("/etc/asterisk/") .. name)
	self[name] = c
	return c
end

function asterisk:write_configs()
	for _, conf in pairs(self.configs) do
		conf:_write()
	end
end

--- Setup default asterisk.conf with our work area directories.
function asterisk:generate_asterisk_conf()
	-- return if it exists already
	if self.configs["asterisk.conf"] then return end

	local c = self:new_config("asterisk.conf")
	local s = c:new_section("directories")
	s["astetcdir"] = self:path("/etc/asterisk")
	s["astmoddir"] = self:path("/usr/lib/asterisk/modules")
	s["astvarlibdir"] = self:path("/var/lib/asterisk")
	s["astdbdir"] = self:path("/var/lib/asterisk")
	s["astkeydir"] = self:path("/var/lib/asterisk")
	s["astdatadir"] = self:path("/var/lib/asterisk")
	s["astagidir"] = self:path("/var/lib/asterisk/agi-bin")
	s["astspooldir"] = self:path("/var/spool/asterisk")
	s["astrundir"] = self:path("/var/run")
	s["astlogdir"] = self:path("/var/log/asterisk")

	s = c:new_section("options")
	s["documentation_language"] = "en_US"
	s["sendfullybooted"]="yes"
	s["verbose"] = 10
	s["debug"] = 10
	s["nocolor"] = "yes"

	s = c:new_section("compat")
	s["pbx_realtime"] = "1.6"
	s["res_agi"] = "1.6"
	s["app_set"] = "1.6"
end

--- Generate logger.conf with debug, messages, and full logs (disable console
-- log).
function asterisk:generate_logger_conf()
	-- return if it exists already
	if self.configs["logger.conf"] then return end

	local c = self:new_config("logger.conf")
	local s = c:new_section("general")
	s = c:new_section("logfiles")
	s["debug"] = "debug"
	s["messages"] = "notice,warning,error"
	s["full"] = "notice,warning,error,debug,verbose,*"
end

--- Generate manager.conf with a unique port.
function asterisk:generate_manager_conf()
	-- return if it exists already
	if self.configs["manager.conf"] then return end

	local c = self:new_config("manager.conf")
	local s = c:new_section("general")
	s["enabled"] = "yes"
	s["bindaddr"] = "0.0.0.0"
	s["port"] = "538" .. self.index

	s = c:new_section("asttest")
	s["secret"] = "asttest"
	s["read"] = "all"
	s["write"] = "all"
end

function asterisk:generate_essential_configs()
	for conf, func in pairs(self.essential_configs) do
		if not self.configs[conf] then
			func(self)
		end
	end
end

function asterisk:dump_full_log()
	local log, err = io.open(self:path("/var/log/asterisk/full"), "r")
	if not log then
		print("error opening '" .. self:path("/var/log/asterisk/full") .. "': " .. err)
	end

	print(log:read("*a"))
	log:close()
end

asterisk_version = {}
function asterisk_version:new(version)
	local v = {
		version = version,
	}
	setmetatable(v, self)
	self.__index = self

	v:_parse()
	return v
end

function asterisk_version:_parse()
	if self.version:sub(1,3) == "SVN" then
		self.svn = true
		self.branch, self.revision, self.parent = self.version:match("SVN%-(.*)%-r(%d+M?)%-(.*)")
		if not self.branch then
			self.branch, self.revision = self.version:match("SVN%-(.*)%-r(%d+M?)")
		end
	else
		self.concept, self.major, self.minor, self.patch = self.version:match("(%d+).(%d+).(%d+).(%d+)")
		if not self.concept then
			self.concept, self.major, self.minor = self.version:match("(%d+).(%d+).(%d+)")
		end
		if not self.concept then
			self.concept, self.major, self.minor = self.version:match("(%d+).(%d+)")
		end
	end
end

function asterisk_version:__tostring()
	return self.version
end

function asterisk_version:__lt(other)
	if self.svn and other.svn then
		-- for svn versions, just compare revisions
		local v1 = tonumber(self.revision:match("(%d)M?"))
		local v2 = tonumber(other.revision:match("(%d)M?"))
		return v1 < v2
	elseif not self.svn and not other.svn then
		-- compare each component of othe version number starting with
		-- the most significant
		local v = {
			{tonumber(self.concept), tonumber(other.concept)},
			{tonumber(self.major), tonumber(other.major)},
			{tonumber(self.minor or 0), tonumber(other.minor or 0)},
			{tonumber(self.patch or 0), tonumber(other.patch or 0)},
		}

		for _, i in ipairs(v) do
			if i[1] < i[2] then
				return true
			elseif i[1] ~= i[2] then
				return false
			end
		end
		return false
	end
	error("cannot compare svn version number with non svn version number")
end

function asterisk_version:__eq(other)
	return self.version == other.version
end

config = {}
function config:from_file(name, src_filename, dst_filename)
	local ac = config:new(name, dst_filename)

	local f, err = io.open(src_filename, "r");
	if not f then
		error("error opening file '" .. src_filename .. "': " .. err)
	end

	ac:verbatim(f:read("*a"))
	f:close()

	return ac
end

function config:new(name, filename)
	local ac = {
		name = name,
		filename = filename or name,
		sections = {},
		section_index = {},
	}
	setmetatable(ac, self)
	return ac
end

function config:verbatim(data)
	table.insert(self.sections, data)
end

function config:add_section(new_section)
	if (getmetatable(new_section) ~= conf_section) then
		error("got " .. type(new_section) .. " expected type conf_section")
	end
	table.insert(self.sections, new_section)
	if not self.section_index[new_section.name] then
		self.section_index[new_section.name] = #self.sections
	end
end

function config:new_section(section_name)
	s = conf_section:new(section_name)
	self:add_section(s)
	return s
end

--- Index the config object
-- This function will return the section of the config indicated if it exists,
-- if it does not exist it will return the table data member with the given
-- name if it exists, otherwise it will create a section with the given name
-- and return that.
function config:__index(key)
	local s = self.sections[self.section_index[key]]
	if s then return s end

	if config[key] ~= nil then
		return config[key]
	end

	return self:new_section(key)
end

function config:_write(filename)
	if not filename then
		filename = self.filename
	end

	-- remove any existing file or symlink
	unlink(filename)

	local f, e = io.open(filename, "w")
	if not f then
		return error("error writing config file: " .. e)
	end

	for _, section in ipairs(self.sections) do
		if getmetatable(section) == conf_section then
			section:_write(f)
		else
			f:write(tostring(section))
		end
	end

	f:close()
end

conf_section = {}
function conf_section:new(name)
	local s = {
		name = name,
		template = false,
		inherit = {},
		values = {},
		value_index = {},
	}
	setmetatable(s, self)
	return s
end

function conf_section:__newindex(key, value)
	table.insert(self.values, {key, value})
	if not self.value_index[key] then
		self.value_index[key] = #self.values
	end
end

function conf_section:__index(key)
	local v = self.values[self.value_index[key]]
	if v then
		return v[2]
	end

	return conf_section[key]
end

function conf_section:_write(f)
	f:write("[" .. self.name .. "]")
	if self.template then
		f:write("(!")
		for _, i in ipairs(self.inherit) do
			f:write("," .. i)
		end
		f:write(")")
	else
		if #self.inherit ~= 0 then
			f:write("(")
			local first = true
			for _, i in ipairs(self.inherit) do
				if not first then
					f:write(",")
				else
					first = false
				end
				f:write(i)
			end
			f:write(")")
		end
	end
	f:write("\n")

	for _, value in ipairs(self.values) do
		f:write(tostring(value[1]) .. " = " .. tostring(value[2]) .. "\n")
	end
	f:write("\n")
end

--
-- Manager Interface Stuff
--

manager = {
	action = {}
}
function manager:new()
	local m = {
		events = {},
		responses = {},
		event_handlers = {},
		response_handlers = {},
		buf = {""},
	}

	setmetatable(m, self)
	self.__index = self
	return m
end

function manager:connect(host, port)
	if not port then
		port = 5038
	end
	local err
	self.sock, err = socket.tcp()
	if not self.sock then
		return nil, err
	end
	local res, err = self.sock:connect(host, port)
	if not res then
		return nil, err
	end

	res, err = self:_parse_greeting()
	if not res then
		self.sock:close()
		return nil, err
	end

	return true
end

function manager:disconnect()
	self.sock:shutdown("both")
	self.sock:close()
	self.sock = nil
end

--- Read data from a socket until a \r\n is encountered.
--
-- Data is read from the socket one character at a time and placed in a table.
-- Once a \r\n is found, the characters are concatinated into a line (minus the
-- \r\n at the end).  Hopefully this prevents the unnecessary garbage
-- collection that would result from appending the characters to a string one
-- at a time as they are read.
local function read_until_crlf(sock)
	local line = {}
	local cr = false
	while true do
		-- reading 1 char at a time is ok as lua socket reads data from
		-- an internal buffer
		local c, err = sock:receive(1)
		if not c then
			return nil, err
		end

		table.insert(line, c)

		if c == '\r' then
			cr = true
		elseif cr and c == '\n' then
			return table.concat(line, nil, 1, #line - 2)
		else
			cr = false
		end
	end
end

function manager:_parse_greeting()
	local line, err = read_until_crlf(self.sock, self.buf)
	if not line then
		return nil, err
	end

	self.name, self.version = line:match("(.+)/(.+)")
	if not self.name then
		return nil, "error parsing manager greeting: " .. line
	end

	return true
end

function manager:_read_message()
	local line, err = read_until_crlf(self.sock, self.buf)
	if not line then
		return nil, err
	end

	local header, value = line:match("([^:]+): (.+)")
	if not header then
		return nil, "error parsing message: " .. line
	end

	local m = manager.message:new()
	m[header] = value
	if header == "Event" then
		table.insert(self.events, m)
	elseif header == "Response" then
		table.insert(self.responses, m)
	else
		return nil, "received unknown message type: " .. header
	end

	local follows = (value == "Follows")
	local data_mode = false
	
	while true do
		line, err = read_until_crlf(self.sock, self.buf)
		if not line then
			return nil, err
		end

		if line == "" and not follows then
			break
		elseif line == "" and follows then
			data_mode = true
		end

		-- don't attempt to match headers when in data mode
		if not data_mode then
			header, value = line:match("([^:]+): ?(.*)")
		else
			header, value = nil, nil
		end

		if not header and not follows then
			return nil, "error parsing message: " .. line
		elseif not header and follows then
			data_mode = true
			if line == "--END COMMAND--" then
				follows = false
				data_mode = false
			else
				m:_append_data(line .. "\n")
			end
		else
			m[header] = value
		end
	end
	return true
end

function manager:_read_response()
	local res, err = self:wait_response()
	if not res then
		return nil, err
	end

	local r = self.responses[1]
	table.remove(self.responses, 1)
	return r
end

function manager:_read_event()
	local res, err = self:wait_event()
	if not res then
		return nil, err
	end

	local e = self.events[1]
	table.remove(self.events, 1)
	return e
end

function manager:pump_messages()
	while true do
		local read, write, err = socket.select({self.sock}, nil, 0)
		if read[1] ~= self.sock or err == "timeout" then
			break
		end

		local res, err = self:_read_message()
		if not res then
			return nil, err
		end
	end
	return true
end

function manager:wait_event()
	while #self.events == 0 do
		local res, err = self:_read_message()
		if not res then
			return nil, err
		end
	end
	return true
end

function manager:wait_response()
	while #self.responses == 0 do
		local res, err = self:_read_message()
		if not res then
			return nil, err
		end
	end
	return true
end

function manager:process_events()
	while #self.events ~= 0 do
		local e = self.events[1]
		table.remove(self.events, 1)

		for event, handlers in pairs(self.event_handlers) do
			if event == e["Event"] then
				for i, handler in ipairs(handlers) do
					handler(e)
				end
			end
		end

		-- now do the catch all handlers
		for event, handlers in pairs(self.event_handlers) do
			if event == "" then
				for i, handler in ipairs(handlers) do
					handler(e)
				end
			end
		end
	end
end

function manager:process_responses()
	while #self.response_handlers ~= 0 and #self.responses ~= 0 do
		local f = self.response_handlers[1]
		table.remove(self.response_handlers, 1);

		f(self:_read_response());
	end
end

function manager:register_event(event, handler)
	local e_handler = self.event_handlers[event]
	if not e_handler then
		self.event_handlers[event] = {}
	end

	table.insert(self.event_handlers[event], handler)
end

function manager:unregister_event(event, handler)
	for e, handlers in pairs(self.event_handlers) do
		if e == event then
			for i, h in pairs(handlers) do
				if h == handler then
					handlers[i] = nil
					if #handlers == 0 then
						self.event_handlers[e] = nil
					end
					return true
				end
			end
		end
	end
	return nil
end

function manager:send_action(action, handler)
	local response = nil
	function handle_response(r)
		response = r
	end

	if handler then
		return self:send_action_async(action, handler)
	end

	local res, err = self:send_action_async(action, handle_response)
	if not res then
		return nil, err
	end

	while not response do
		res, err = self:wait_response()
		if not res then
			return nil, err
		end
		self:process_responses()
	end
	return response
end
manager.__call = manager.send_action

function manager:send_action_async(action, handler)
	local res, err, i = nil, nil, 0
	local a = action:_format()
	
	while i < #a do
		res, err, i = self.sock:send(a, i + 1)
		if err then
			return nil, err
		else
			i = res
		end
	end
	table.insert(self.response_handlers, handler)
	return true
end


--
-- Manager Helpers
--

manager.message = {}
function manager.message:new()
	local m = {
		headers = {},
		index = {},
		data = nil,
	}
	setmetatable(m, self)
	return m
end

function manager.message:__newindex(key, value)
	table.insert(self.headers, {key, value})
	if not self.index[key] then
		self.index[key] = #self.headers
	end
end

function manager.message:__index(key)
	if self.index[key] then
		return self.headers[self.index[key]][2]
	end

	return manager.message[key]
end

function manager.message:_format()
	local msg = ""
	for i, header in ipairs(self.headers) do
		msg = msg .. header[1] .. ": " .. header[2] .. "\r\n"
	end
	msg = msg .. "\r\n"
	return msg
end

function manager.message:_append_data(data)
	if not self.data then
		rawset(self, "data", data)
	else
		self.data = self.data .. data
	end
end

function manager.action:new(action)
	local a = manager.message:new()

	-- support ast.manager.action.new() syntax
	-- XXX eventually this should be the only syntax allowed
	if action == nil and type(self) == "string" then
		action = self
	end

	a["Action"] = action
	return a
end

-- some utility functions to access common manager functions are defined below

--- Create a login action.
-- This function creates a login action.  When called with no arguments, the
-- default 'asttest', 'asttest' username secret is used.
--
-- @param username the username to send (defaults to 'asttest')
-- @param secret the secret to send (defaults to 'asttest')
function manager.action.login(username, secret)
	local a = manager.action.new("Login")

	username = username or "asttest"
	secret = secret or "asttest"

	a["Username"] = username
	a["Secret"] = secret

	return a
end

--- Create a logoff action.
function manager.action.logoff()
	return manager.action.new("Logoff")
end

