function sipp_exec(scenario, local_port)
	return proc.exec_io("sipp",
	"127.0.0.1",
	"-m", "1",
	"-sf", scenario,
	"-i", "127.0.0.1",
	"-p", local_port,
	"-timeout", "30",
	"-trace_err"
	)
end

function sipp_exec_and_wait(scenario, name, local_port)
	return sipp_check_error(sipp_exec(scenario, name, local_port), scenario)
end

function sipp_check_error(p, scenario)
	local res, err = p:wait()

	if not res then error(err) end
	if res ~= 0 then
		error("error while executing " .. scenario .. " sipp scenario (sipp exited with status " .. res .. ")\n" .. p.stderr:read("*a"))
	end

	return res, err
end

function varset_event_one(event)
	if (event["Variable"] == "READRESULT") then
		if (event["Value"] ~= "1") then
			fail("Wrong UAS answered. Expected DTMF '1' but received " .. event["Value"])
		else
			passed = true;
		end
	end
end

function varset_event_two(event)
	if (event["Variable"] == "READRESULT") then
		if (event["Value"] ~= "2") then
			fail("Wrong UAS answered. Expected DTMF '2' but received " .. event["Value"])
		else
			passed = true;
		end
	end
end

function manager_setup(a)
	m,err = a:manager_connect()
	if not m then
		fail("error connecting to asterisk: " .. err)
	end

	login = ast.manager.action:new("login")
	login["Username"] = "asttest"
	login["Secret"] = "asttest"

	local r = m(login)
	if not r then
		fail("error logging in to the manager: " .. err)
	end

	if r["Response"] ~= "Success" then
		fail("error authenticating: " .. r["Message"])
	end
end

function setup_uas()
	local t1 = sipp_exec("sipp/uas1.xml", "5061")
	local t2 = sipp_exec("sipp/uas2.xml", "5062")
	return t1, t2
end

function kill_uas(t1, t2)
	t1:term_or_kill()
	t2:term_or_kill()
end

function test_call(exten, handler)
	passed = false;
	m:register_event("VarSet", handler)
	local uas1, uas2 = setup_uas()
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/" .. exten .. "@test_context"
	orig["Context"] = "test_context"
	orig["Application"] = "Wait"
	orig["Data"] = "1"
	local res, err = m(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Response failure for Originate: " .. res["Message"])
	end
	posix.sleep(2)
	local res, err = m:pump_messages()
	if not res then
		fail("error pumping manager messages: " .. err)
	end
	m:process_events()
	m:unregister_event("VarSet", handler)
	kill_uas(uas1, uas2)
	if not passed then
		fail("Failure has occurred")
	end
end

a = ast.new()
a:load_config("configs/ast1/sip.conf")
a:load_config("configs/ast1/extensions.conf")
a:generate_manager_conf()
a:spawn()

manager_setup(a)

test_call("test1", varset_event_one)
test_call("test2", varset_event_two)
test_call("test3", varset_event_two)
test_call("test4", varset_event_two)
test_call("test5", varset_event_two)
test_call("test6", varset_event_one)

a:term_or_kill()
