function manager_setup(a)
	local m,err = a:manager_connect()
	if not m then
		fail("error connecting to asterisk: " .. err)
	end

	login = ast.manager.action.login()
	if not login then
		fail("Couldn't create login?")
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

booted = nil
function boot_event(event)
	booted = true
end

function wait_until_booted(man)
	man:register_event("FullyBooted", boot_event)
	while not booted do
		local res, err = man:wait_event()
		if not res then
			fail("Failure while waiting for FullyBooted event: " .. err)
		end
		man:process_events()
	end
	man:unregister_event("FullyBooted", boot_event)
end

function member1(event)
	--Userful for debugging
	--print("Got member1")
	--print("Queue: " .. tostring(event["Queue"]))
	--print("Uniqueid: " .. tostring(event["Uniqueid"]))
	--print("Channel: " .. tostring(event["Channel"]))
	--print("Member: " .. tostring(event["Member"]))
	--print("MemberName: " .. tostring(event["MemberName"]))
	--print("Holdtime: " .. tostring(event["Holdtime"]))
	--print("BridgedChannel: " .. tostring(event["BridgedChannel"]))
	--print("Ringtime: " .. tostring(event["Ringtime"]))
	if event["MemberName"] == "member1" then
		pass = true
	else
		print(event["Membername"])
	end
end

function member2(event)
	--print("Got member2")
	--print("Queue: " .. tostring(event["Queue"]))
	--print("Uniqueid: " .. tostring(event["Uniqueid"]))
	--print("Channel: " .. tostring(event["Channel"]))
	--print("Member: " .. tostring(event["Member"]))
	--print("MemberName: " .. tostring(event["MemberName"]))
	--print("Holdtime: " .. tostring(event["Holdtime"]))
	--print("BridgedChannel: " .. tostring(event["BridgedChannel"]))
	--print("Ringtime: " .. tostring(event["Ringtime"]))
	if event["MemberName"] == "member2" then
		pass = true
	end
end

function setup_ast_instance(which)
	local instance = ast.new()
	instance:load_config("configs/extensions.conf")
	instance:load_config("configs/" .. which .. "/queues.conf")
	instance:generate_manager_conf()
	instance:spawn()
	return instance
end

function test_call(ast_instance, man, handler, exten)
	if handler then
		man:register_event("AgentConnect", handler)
		pass = false
	end
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/" .. exten .. "@test_context/n"
	orig["Application"] = "Wait"
	orig["Data"] = "1"
	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end

	if res["Response"] ~= "Success" then
		if not handler then
			--When the handler is nil, this means we expect that no
			--queue members will be available to answer the call. Since
			--no one can answer the originated call, the originate will
			--fail. If it doesn't, then something went wrong.
			return
		else
			fail("Response failure for Originate: " .. res["Message"])
		end
	elseif not handler then
		fail("Originate successful when there should have been no available queue members")
	end

	posix.sleep(1)

	res, err = man:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end

	man:process_events()
	if not pass then
		if handler == member1 then
			fail("Did not get AgentConnect for member1 as expected")
		elseif handler == member2 then
			fail("Did not get AgentConnect for member2 as expected")
		else
			fail("Got AgentConnect when we should not have gotten one")
		end
	end
	man:unregister_event("AgentConnect", handler)
end

instance1 = setup_ast_instance("ast1")
instance2 = setup_ast_instance("ast2")

posix.sleep(1)

man1 = manager_setup(instance1)
man2 = manager_setup(instance2)

wait_until_booted(man1)
wait_until_booted(man2)

test_call(instance1, man1, member1, "test1")
test_call(instance1, man1, member1, "test2")
test_call(instance1, man1, member2, "test1")
test_call(instance2, man2, member1, "test1")
test_call(instance2, man2, member2, "test2")
--On this call, since both members are unavailable,
--originating a call to the queue will fail since
--no one will answer
test_call(instance2, man2, nil, "test1")
logoff = ast.manager.action.logoff()
man1(logoff)
logoff = ast.manager.action.logoff()
man2(logoff)
instance1:term_or_kill()
instance2:term_or_kill()
