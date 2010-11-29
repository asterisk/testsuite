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

function manager_setup(a)
	m,err = a:manager_connect()
	if not m then
		fail("error connecting to asterisk: " .. err)
	end

	local login = ast.manager.action:new("login")
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

function findpattern(text, pattern, start)
	return string.sub(text, string.find(text, pattern, start))
end

function check_sip_params(sip_params, chan_name)
	for key,value in pairs(sip_params) do
		local variable = "CHANNEL(" .. key .. ")"
		local getvar = ast.manager.action:new("GetVar")
		getvar["Channel"] = chan_name
		getvar["Variable"] = variable
		local response, err = m(getvar)
		if not response then
			fail("error getting variable " .. key .. ": " .. err)
			break
		end
		if response["Response"] ~= "Success" then
			fail("Response failure: " .. response["Message"])
		end
		if response["Variable"] ~= variable then
			fail("Wrong variable. Expected " .. variable .. " but got " .. response["Variable"])
		end
		--Helpful for debugging in case this test starts failing
		--print ("Got value " ..  response["Value"] .. " for variable " .. response["Variable"])
		if not findpattern(response["Value"], value) then
			fail("Expected " .. value .. " for variable " .. response["Variable"] .. " but got " .. response["Value"])
		end
	end
end

function get_channel_name()
	local chan_name = nil
	local function set_name(event)
		chan_name = event["Channel"]
	end
	m:register_event("Newchannel", set_name)
	local res, err = m:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end
	m:process_events()
	m:unregister_event("Newchannel", set_name)
	return chan_name
end

function test_call(scenario, name, local_port, sip_params)
	local t1 = sipp_exec(scenario, name, local_port)
	local chan_name = nil

	posix.sleep(1)
	chan_name = get_channel_name()
	if not chan_name then
		fail("Failed to get the name of the channel\n");
	else
		print("Got channel name " .. chan_name)
	end
	check_sip_params(sip_params, chan_name)
	-- We have what we want. Let the scenario conclude
	sipp_check_error(t1, scenario)
end

function call_and_check_sip_params(name)
	local a = ast.new()
	local sip_params = {
		["peerip"] = "127.0.0.1",
		["recvip"] = "127.0.0.1",
		["from"] = "sip:wienerschnitzel@127.0.0.1:5061",
		["uri"] = "sip:kartoffelsalat@127.0.0.1:5061",
		["useragent"] = "Channel Param Test",
		["peername"] = "test1",
		["t38passthrough"] = "0",
		["rtpdest,audio"] = "127.0.0.1:6000",
		["rtpdest,video"] = "127.0.0.1:6002",
		["rtpdest,text"] = "",
		--We have no way to force a specific source
		--RTP port to be used; we can specify only a
		--range. Thus, our rtp.conf file limits the
		--audio and video RTP ports to a selection of
		--either 10000 or 10002.
		["rtpsource,audio"] = "127.0.0.1:1000[02]",
		["rtpsource,video"] = "127.0.0.1:1000[02]",
		["rtpsource,text"] = ""
	}

	a:load_config("configs/ast1/sip.conf")
	a:load_config("configs/ast1/extensions.conf")
	a:load_config("configs/ast1/rtp.conf")
	a:generate_manager_conf()
	a:spawn()

	manager_setup(a)
	--register our peer
	sipp_exec_and_wait("sipp/register.xml", name, "5061")

	test_call("sipp/call.xml", name, "5061", sip_params)
end

call_and_check_sip_params("test1")
