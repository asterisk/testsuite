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

function new()
	return asterisk:new()
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

function asterisk:spawn()
	self:clean_work_area()
	self:create_work_area()
	self:generate_essential_configs()
	self:write_configs()
	self:_spawn()
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

function asterisk:__index(key)
	if self.configs[key] then
		return self.configs[key]
	end

	return asterisk[key]
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
	s["full"] = "notice,warning,error,debug,verbose"
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

function config:__index(key)
	local s = self.sections[self.section_index[key]]
	if s then return s end

	return config[key]
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

function manager:_parse_greeting()
	local line, err = self.sock:receive("*l")
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
	local line, err = self.sock:receive("*l")
	if not line then
		return nil, err
	end

	local header, value = line:match("(.+): (.+)")
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
	
	while true do
		line, err = self.sock:receive("*l")
		if not line then
			return nil, err
		end

		if line == "" then
			break
		end

		header, value = line:match("(.+): (.+)")
		if not header and not follows then
			return nil, "error parsing message: " .. line
		elseif not header and follows then
			if line ~= "--END COMMAND--" then
				m._append_data(line .. "\n")
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
		for event, handler in pairs(self.event_handlers) do
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
		self.data = data
	else
		self.data = self.data .. data
	end
end

function manager.action:new(action)
	local a = manager.message:new()
	a["Action"] = action
	return a
end


