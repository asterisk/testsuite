require "watcher"

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

function do_call(man)
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/test@test_context"
	orig["Exten"] = "queue"
	orig["Context"] = "test_context"
	orig["Priority"] = "1"

	local e = watcher.event.new;
	local events = watcher.etree:new{
		e("Join"),
		e("AgentCalled"),
		e("AgentConnect"),
		e("Leave"),
		e("AgentComplete"),
	}

	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Response failure for Originate: " .. res["Message"])
	end
	
	res, err = watcher.watch(man, events, 10000)
	if not res then
		print("Error matching events (" .. err .. ")")
		print "Expected (not ordered):"
		print "   Join"
		print "   AgentCalled"
		print "   AgentConnect"
		print "   Leave"
		print "   AgentComplete"
		print "\nReceived:"

		for _, e in pairs(events.multi) do
			print("   " .. e["Event"])
		end

		print ""

		fail()
	end
end

instance = ast.new()
instance:load_config("configs/ast1/extensions.conf")
instance:load_config("configs/ast1/queues.conf")
instance:load_config("configs/ast1/modules.conf")
instance:generate_manager_conf()
instance:spawn()

man = manager_setup(instance)

do_call(man)
man(ast.manager.action.logoff())
instance:term_or_kill()

