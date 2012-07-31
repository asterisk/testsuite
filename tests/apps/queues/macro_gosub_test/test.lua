function manager_setup(a)
	local m,err = a:manager_connect()
	if not m then
		fail("error connecting to asterisk: " .. err)
	end

	local login = ast.manager.action.login()
	if not login then
		fail("Failed to create manager login action")
	end

	local r = m(login)
	if not r then
		fail("error logging in to the manager: " .. err)
	end

	if r["Response"] ~= "Success" then
		fail("error authenticating: " .. r["Message"])
	end
	return m
end

function primary(event)
	if event["Variable"] == "MACROVAR" then
		if event["Value"] == "primarymacro" then
			passmacro = true
		end
	end
	if event["Variable"] == "GOSUBVAR" then
		if event["Value"] == "primarygosub" then
			passgosub = true
		end
	end
end

function secondary(event)
	if event["Variable"] == "MACROVAR" then
		if event["Value"] == "secondarymacro" then
			passmacro = true
		end
	end
	if event["Variable"] == "GOSUBVAR" then
		if event["Value"] == "secondarygosub" then
			passgosub = true
		end
	end
end

function test_call(exten, man, handler)
	passmacro = false
	passgosub = false
	local orig = ast.manager.action:new("Originate")
	man:register_event("VarSet", handler)
	orig["Channel"] = "Local/" .. exten .."@test_context/n"
	orig["Application"] = "Wait"
	orig["Data"] = "3"

	local res,err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end

	if res["Response"] ~= "Success" then
		fail("Failure response from Originate: " .. res["Message"])
	end

	--When the originate returns, we know that the member
	--has answered the call, but we can't guarantee that
	--the macro or gosub has actually run, so sleep for a
	--sec for safety's sake
	posix.sleep(1)
	res, err = man:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end

	man:process_events()
	man:unregister_event("VarSet", handler)

	if not passmacro then
		fail("Did not get expected macro variable set")
	end

	if not passgosub then
		fail("Did not get expected gosub variable set")
	end
end

instance = ast.new()
instance:load_config("configs/ast1/extensions.conf")
instance:load_config("configs/ast1/queues.conf")
instance:generate_manager_conf()
instance:spawn()

man = manager_setup(instance)

test_call("test1", man, primary)
test_call("test2", man, secondary)

logoff = ast.manager.action.logoff()
man(logoff)
instance:term_or_kill()
