function mcheck(msg, r, err)
	check(msg, r, err)
	if r["Response"] ~= "Success" then
		if r["Message"] then
			error(msg .. ": " .. r["Message"])
		else
			error(msg)
		end
	end

	return r, err
end

action = ast.manager.action

-- limit the manager to 5 connections
limit = 5

print("starting asterisk")
a = ast.new()
a:generate_manager_conf()
a["manager.conf"]["general"]["authlimit"] = limit
a:spawn()

clients = {}

print("connecting " .. limit .. " clients to asterisk")
for i = 1, limit do
	local m = check("error connecting client " .. i .. " to asterisk", a:manager_connect())
	table.insert(clients, m)
end

print("attempting to connect one more, this should fail")
fail_if(a:manager_connect(), "client " .. limit + 1 .. " successfully connected, this should have failed")

for _, m in ipairs(clients) do
	m:close()
end

posix.sleep(3) -- let the connections shut down

print("connecting and authenticating " .. limit .. " clients to asterisk")
for i = 1, limit do
	local m = check("error connecting client " .. i .. " to asterisk", a:manager_connect())
	mcheck("error authenticating client " .. i, m(action.login()))
	table.insert(clients, m)
end

print("attempting to connect one more, this should succeed")
fail_if(not a:manager_connect(), "client " .. limit + 1 .. " failed to connect")

