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

-- timeout after 5 seconds by default
timeout = 5

print("starting asterisk")
a = ast.new()
a:generate_manager_conf()
a["manager.conf"]["general"]["authtimeout"] = timeout
a:spawn()

print("testing timeout of an unauthenticated session")
m = check("error connecting to asterisk", a:manager_connect())
posix.sleep(timeout + 1)
fail_if(m:pump_messages(), "asterisk did not close the connection after " .. timeout .. " seconds")

print("testing timeout of an authenticated session (should not timeout)")
m = check("error connecting to asterisk", a:manager_connect())
mcheck("error logging in to asterisk", m(action.login()))
posix.sleep(timeout * 2)
fail_if(not m:pump_messages(), "asterisk timedout after successful authentication")

