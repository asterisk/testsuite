module(..., package.seeall)

event = {}
function event.new(event)
	local e = ast.manager.message:new()
	e["Event"] = event
	return e
end


etree = {}
etree.__index = etree
function etree:new(expect)
	local e = {
		expect = expect,
		c = nil, -- children
		multi = {},
		received = nil,
	}

	setmetatable(e, self)
	return e
end

function etree:__tostring()
	return self:_print()
end

function etree:_print(prefix)
	local result = ""
	if not prefix then prefix = "" end

	if getmetatable(self.expect) == nil
	and type(self.expect) == 'table' then
		result = result .. prefix .. "{"
		for i, event in ipairs(self.expect) do
			if i == 1 then
				result = result .. event["Event"] 
			else
				result = result .. ", " .. event["Event"]
			end
		end

		result = result .. "}\n"
	else
		result = result .. prefix .. self.expect["Event"] .. "\n"
	end

	if self.c then
		for i, etree in ipairs(self.c) do
			result = result .. etree:_print(prefix .. "  ")
		end
	end

    return result
end

function etree:add(child)
	if getmetatable(child) ~= etree then
		child = etree:new(child)
	end

	if not self.c then
		self.c = {child}
	else
		table.insert(self.c, child)
	end
	return child
end

function etree:check_all(e)
	if getmetatable(self.expect) == nil
	and type(self.expect) == 'table' then
		local res = false
		for i, expect in ipairs(self.expect) do
			if not self.multi[i] and self:check(e, expect) then
				self.multi[i] = e
				res = true
				break
			end
		end

		self.received = self.multi
		for i, _ in ipairs(self.expect) do
			if not self.multi[i] then
				self.received = nil
			end
		end

		return res
	end

	if self:check(e, self.expect) then
		self.received = e
		return true
	end

	return false
end

function etree:check(e, expect)
	if type(expect) == 'function' then
		return expect(e)
	end

	if e["Event"] == expect["Event"] then
		local matched = true
		for i, h in ipairs(expect.headers) do
			local found = false
			for i, h2 in ipairs(e.headers) do
				if h[1] == h2[1] then
					if type(h[2]) == 'function' then
						local res = h[2](h2[2])
						if res then
							found = true
							break
						end
					elseif h[2] == h2[2] then
						found = true
						break
					end
				end
			end
			if not found then
				matched = false
				break
			end
		end
		return matched
	end

	return false
end

function etree:check_next(e)
	if not self.received then
		return self:check_all(e)
	end
	
	if self.c then
		for i, etree in ipairs(self.c) do
			if etree:check_next(e) then
				return true
			end
		end
	end

	return false
end

function etree:matched()
	-- if this node has not been matched, return false
	if not self.received then
		return false
	end

	-- if this node has been matched and has no children, return true
	if not self.c then
		return true
	end

	-- check if any of the children have been matched
	if self.c then
		for i, e in ipairs(self.c) do
			if e:matched() then
				return true
			end
		end
	end

	-- none of the children matched
	return false
end

--- Watch the given manager connection for the given events within the given
-- time period.
-- @returns True on success and nil and an error message on failure.  Currently
-- the only error message is "timeout".
function watch(m, tree, timeout)
	local rough_seconds = 0

	if getmetatable(tree) == watcher.etree then
		tree = {tree}
	end

	function matched()
		for i, e in ipairs(tree) do
			if not e:matched() then
				return false
			end
		end
		return true
	end

	function handle_events(event)
		for i, e in ipairs(tree) do
			if e:check_next(event) then
				break
			end
		end
	end

	m:register_event("", handle_events)
	while not matched() do
		if timeout ~= 0 and rough_seconds >= timeout then
			m:unregister_event("", handle_events)
			return nil, "timeout"
		end

		local res, err = m:pump_messages()
		if not res then
			m:unregister_event("", handle_events)
			error("error processing events: " .. err)
		end

		m:process_events()

		if timeout == 0 then
			return nil, "timeout"
		end

		posix.sleep(1)

		rough_seconds = rough_seconds + 1
	end

	m:unregister_event("", handle_events)
	return tree
end
