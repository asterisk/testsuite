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

	result = result .. prefix .. self.expect["Event"] .. "\n"

	if self.c then
		for i, etree in ipairs(self.c) do
			result = result .. etree:_print(prefix .. "   ")
		end
	end

    return result
end

function etree:add(child)
	if getmetatable(child) == ast.manager.message then
		child = etree:new(child)
	end

	if not self.c then
		self.c = {child}
	else
		table.insert(self.c, child)
	end
	return child
end

function etree:check(e)
	if type(self.expect) == 'function' then
		local res = self.expect(e)
		if res then
			self.received = e
		end
		return res
	end

	if e["Event"] == self.expect["Event"] then
		local matched = true
		for i, h in ipairs(self.expect.headers) do
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
		if matched then
			self.received = e
		end
		return matched
	end

	return false
end

function etree:check_next(e)
	if not self.received then
		return self:check(e)
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
	if not self.received then
		return false
	end

	if self.c then
		for i, e in ipairs(self.c) do
			if not e:matched() then
				return false
			end
		end
	end

	return true
end

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
		if rough_seconds > timeout then
			m:unregister_event("", handle_events)
			return nil, "timeout"
		end

		local res, err = m:pump_messages()
		if not res then
			m:unregister_event("", handle_events)
			error("error processing events: " .. err)
		end

		m:process_events()
		posix.sleep(1)

		rough_seconds = rough_seconds + 1
	end

	m:unregister_event("", handle_events)
	return tree
end
