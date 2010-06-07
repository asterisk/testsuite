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

join = nil
function join_event(event)
	join = 1
end

called = nil
function called_event(event)
	called = 1
end

connect = nil
function connect_event(event)
	connect = 1
end

leave = nil
function leave_event(event)
	leave = 1
end

complete = nil
function complete_event(event)
	complete = 1
end

function do_call(man)
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/test@test_context"
	orig["Exten"] = "queue"
	orig["Context"] = "test_context"
	orig["Priority"] = "1"
	man:register_event("Join", join_event)
	man:register_event("AgentCalled", called_event)
	man:register_event("AgentConnect", connect_event)
	man:register_event("Leave", leave_event)
	man:register_event("AgentComplete", complete_event)
	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Response failure for Originate: " .. res["Message"])
	end
	posix.sleep(3)
	res, err = man:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end
	man:process_events()
	man:unregister_event("Join", join_event)
	man:unregister_event("AgentCalled", called_event)
	man:unregister_event("AgentConnect", connect_event)
	man:unregister_event("Leave", leave_event)
	man:unregister_event("AgentComplete", complete_event)
end

instance = ast.new()
instance:load_config("configs/extensions.conf")
instance:load_config("configs/queues.conf")
instance:generate_manager_conf()
instance:spawn()

man = manager_setup(instance)

do_call(man)
logoff = ast.manager.action.logoff()
man(logoff)
instance:term_or_kill()

if not join then
	print "Failed to capture Join event"
end
if not called then
	print "Failed to capture AgentCalled event"
end
if not connect then
	print "Failed to capture AgentConnect event"
end
if not leave then
	print "Failed to capture Leave event"
end
if not complete then
	print "Failed to capture AgentComplete event"
end

if not join or not called or not connect or not leave or not complete then
	fail("Failed to capture one of our expected events")
end
