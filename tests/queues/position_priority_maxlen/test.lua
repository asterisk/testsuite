function manager_setup(a)
	local m, err = a:manager_connect()
	if not m then
		fail("error connecting to asterisk: " .. err)
	end

	login = ast.manager.action.login()
	if not login then
		fail("Couldn't create login?")
	end

	local r, err = m(login)
	if not r then
		fail("error logging in to the manager: " .. err)
	end

	if r["Response"] ~= "Success" then
		fail("error authenticating: " .. r["Message"])
	end
	return m
end

function setup_ast_instance()
	local instance = ast.new()
	instance:load_config("configs/extensions.conf")
	instance:load_config("configs/queues.conf")
	instance:generate_manager_conf()
	instance:spawn()
	return instance
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

function join_event(event)
	actual_position = tonumber(event["Position"])
end

function test_call(priority, position, expected_position)
	local prio_string = ""
	local pos_string = ""
	local comma = ""
	actual_position = nil
	man:register_event("Join", join_event)
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/test@test_context/n"
	orig["Application"] = "Wait"
	orig["Data"] = "100"
	if priority then
		prio_string = "QUEUE_PRIO=" .. priority
	end
	if position then
		pos_string = "QUEUE_POS=" .. position
	end
	if position and priority then
		comma = ","
	end
	orig["Variable"] = pos_string .. comma .. prio_string
	local res, err = man(orig)
	if not res then
		fail("Failed to send originate: " .. err)
	end

	if res["Response"] ~= "Success" then
		fail("Originate response is an error: " .. res["Message"])
	end
	posix.sleep(1)
	res, err = man:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end
	man:process_events()
	man:unregister_event("Join", join_event)
	if actual_position ~= expected_position then
		fail("Expected caller to enter at position " .. tostring(expected_position) .. " but entered at " .. tostring(actual_position))
	end
end

instance = setup_ast_instance()
man = manager_setup(instance)
wait_until_booted(man)
test_call(nil, nil, 1) --1
test_call(nil, nil, 2) --1,2
test_call(1, nil, 1)   --3,1,2
test_call(1, nil, 2)   --3,4,1,2
test_call(2, nil, 1)   --5,3,4,1,2
test_call(nil, 5, 5)   --5,3,4,1,6,2
test_call(nil, 200, 7) --5,3,4,1,6,2,7
test_call(nil, 1, 4)   --5,3,4,8,1,6,2,7
test_call(8, 3, 1)     --9,5,3,4,8,1,6,2,7
test_call(1, 7, 5)     --9,5,3,4,10,8,1,6,2,7
test_call(1, 4, 4)     --9,5,3,11,4,10,8,1,6,2,7
test_call(2, 5, nil)   --Can't enter due to maxlen
logoff = ast.manager.action.logoff()
man(logoff)
instance:term_or_kill()
