function sipp_exec(scenario, local_port)
	return proc.exec_io("sipp",
	"127.0.0.1",
	"-sf", scenario,
	"-i", "127.0.0.1",
	"-m", "1",
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


function manager_setup(a)
	local m, err = a:manager_connect()
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

function setup_ast_instance()
	local instance = ast.new()
	instance:load_config("configs/ast1/extensions.conf")
	instance:load_config("configs/ast1/queues.conf")
	instance:load_config("configs/ast1/pjsip.conf")
	instance:generate_manager_conf()
	instance:spawn()
	return instance
end

function get_chan_name(event)
	chan_name = event["Channel"]
end

function busy_the_member(man)
	man:register_event("Newchannel", get_chan_name)
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "SIP/member"
	orig["Application"] = "Wait"
	orig["Data"] = "15"
	orig["Async"] = "yes"
	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Originate response failure when trying to busy the member")
	end

	local i = 0
	while not chan_name and i < 30 do
		res, err = man:pump_messages()
		if not res then
			fail("Failure while waiting to get channel name")
		end
		man:process_events()
		i = i + 1;
		posix.sleep(1)
	end
	if not chan_name then
		fail("Failed to get channel name after waiting 30 seconds")
	end
	man:unregister_event("Newchannel", get_chan_name)
end

function unbusy_the_member(man)
	local hangup = ast.manager.action:new("Hangup")
	hangup["Channel"] = chan_name
	local res, err = man(hangup)
	if not res then
		fail("Error trying to hang up call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Response failure from hangup: " .. res["Message"])
	end
end

function agent_called_handler(event)
	actual_call_result = true
end

function agent_paused_handler(event)
	actual_pause_result = true
end

function test_call(queue, originate_result, expected_call_result, pause_expectation)
	local orig = ast.manager.action:new("Originate")
	actual_call_result = false
	actual_pause_result = false
	man:register_event("AgentCalled", agent_called_handler)
	man:register_event("QueueMemberPaused", agent_paused_handler)
	orig["Channel"] = "Local/" .. queue .. "@test_context/n"
	orig["Application"] = "Wait"
	orig["Data"] = "3"
	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	--For calls to the queue where no member is
	--available to answer, we expect the originate
	--to fail.
	if res["Response"] ~= originate_result then
		fail("Unexpected originate result. Expected " .. originate_result .. " but got " .. res["Response"])
	end

	local i = 0
	while actual_call_result ~= expected_call_result or actual_pause_result ~= pause_expectation and i < 30 do
		res, err = man:pump_messages()
		if not res then
			fail("Failure to pump messages")
		end
		man:process_events()
		i = i + 1
		posix.sleep(1)
	end

	if actual_call_result ~= expected_call_result then
		fail("Unexpected AgentCalled result. Got " .. tostring(actual_call_result) .." but expected " .. tostring(expected_call_result))
	end

	if actual_pause_result ~= pause_expectation then
		fail("Unexpected QueueMemberPaused result")
	end
	man:unregister_event("AgentCalled", agent_called_handler)
	man:unregister_event("QueueMemberPaused", agent_paused_handler)
end

sipp_proc = sipp_exec("sipp/uas.xml", "5061")
a = setup_ast_instance()
man = manager_setup(a)
chan_name = nil

busy_the_member(man)
--Since the member is busy, we won't actually ever
--call, and therefore we won't autopause the guy
--either.
test_call("queue1", "Error", false, false)
--This queue allows ringinuse, but the member
--is in use when we call. The result is that
--we will actually attempt to call the member up, so
--we will get an AgentCalled event. Since we
--did try calling, we will also autopause the
--jerk.
test_call("queue2", "Error", true, true)
unbusy_the_member(man)
sipp_check_error(sipp_proc, "sipp/uas.xml")
sipp_proc = sipp_exec("sipp/uas.xml", "5061")
--Sleep for a bit to ensure scenario is up and running
posix.sleep(1)
--Now the member is available. A call from
--the first queue will work perfectly.
test_call("queue1", "Success", true, false)
--Have to restart the scenario since
--it ends after a hangup
sipp_check_error(sipp_proc, "sipp/uas.xml")
sipp_proc = sipp_exec("sipp/uas.xml", "5061")
--Sleep for a bit to ensure scenario is up and running
posix.sleep(1)
--However, the member is paused in this queue,
--so we should see no call attempt get made
--at all.
test_call("queue2", "Error", false, false)
logoff = ast.manager.action.logoff()
man(logoff)
a:term_or_kill()
