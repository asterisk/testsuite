function sipp_exec(scenario, name, local_port)
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
		if (event["Value"] ~= "123456789*") then
			fail("DTMF not detected properly. Expected '123456789*' but received " .. event["Value"])
		end
	end
end

function varset_event_two(event)
	if (event["Variable"] == "READRESULT") then
		if (event["Value"] ~= "1000") then
			fail("DTMF not detected properly. Expected '1000' but received " .. event["Value"])
		end
	end
end

function varset_event_three(event)
	if (event["Variable"] == "READRESULT") then
		if (event["Value"] ~= "1234") then
			fail("DTMF not detected properly. Expected '1234' but received " .. event["Value"])
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

function test_call(scenario, handler, name, local_port)
	m:register_event("VarSet", handler)
	local t1 = sipp_exec(scenario, name, local_port)

	--wait for everything to finish
	sipp_check_error(t1, scenario)
	posix.sleep(1)
	local res, err = m:pump_messages()
	if not res then
		fail("error pumping manager messages: " .. err)
	end
	m:process_events()
	m:unregister_event("VarSet", handler)
end

function do_dtmf_and_check_results(name)
	local a = ast.new()
	a:load_config("configs/ast1/sip.conf")
	a:load_config("configs/ast1/extensions.conf")
	a:load_config("configs/ast1/rtp.conf")
	a:generate_manager_conf()
	a:spawn()

	manager_setup(a)

	--register our peer
	sipp_exec_and_wait("sipp/register.xml", name, "5061")

	test_call("sipp/dtmf_baseline.xml", varset_event_one, name, "5061")
	test_call("sipp/broken_dtmf.xml", varset_event_two, name, "5061")
	test_call("sipp/dtmf_noend.xml", varset_event_three, name, "5061")

	a:term_or_kill()
end

do_dtmf_and_check_results("test1")
