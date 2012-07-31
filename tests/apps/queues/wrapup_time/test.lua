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
		connectpass = true
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
		connectpass = true
	else
		print(event["Membername"])
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

function complete_handler(event)
	completepass = true
end

function test_call(ast_instance, man, handler, exten)
	if handler then
		man:register_event("AgentConnect", handler)
		man:register_event("AgentComplete", complete_handler)
		connectpass = false
		completepass = false
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

	--This loop is constructed so that we will wait for the call to
	--finish before moving on. We'll only wait a maximum of 30 iterations
	--though. And since there is a 1 second sleep on each iteration, that
	--comes out to about 30 seconds.
	i = 0
	while not completepass or not connectpass and i < 30 do
		res, err = man:pump_messages()
		if not res then
			fail("Failure while waiting for event" .. err)
		end
		man:process_events()
		i = i + 1;
		posix.sleep(1)
	end

	if not connectpass then
		fail("Failed to receive an AgentConnect event within 30 seconds")
	end

	if not completepass then
		fail("Failed to receive an AgentComplete event within 30 seconds")
	end

	man:unregister_event("AgentConnect", handler)
	man:unregister_event("AgentComplete", complete_handler)
end

instance1 = setup_ast_instance("ast1")
instance2 = setup_ast_instance("ast2")

man1 = manager_setup(instance1)
man2 = manager_setup(instance2)

test_call(instance1, man1, member1, "test1")
posix.sleep(1)
test_call(instance1, man1, member1, "test2")
posix.sleep(1)
test_call(instance1, man1, member2, "test1")
posix.sleep(1)
test_call(instance2, man2, member1, "test1")
posix.sleep(1)
test_call(instance2, man2, member2, "test2")
posix.sleep(1)
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
