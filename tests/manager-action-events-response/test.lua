
function check_err(msg, r, err)
	if not r then
		error(msg .. ": " .. err)
	end
	return r
end

function test_events_response(asterisk, event_mask, expected_response)
	local got_response

	print("sending 'EventMask: " .. event_mask .. "'")

	local m = check_err("error connecting to asterisk", asterisk:manager_connect())

	local r = check_err("error authenticating", m(action.login()))
	if r["Response"] ~= "Success" then
		error("error authenticating: " .. r["Message"])
	end


	local ma = action.new("Events")
	ma["EventMask"] = event_mask

	function handle_response(r)
		got_response = r
	end

	-- send an Events action
	r = check_err("error sending 'Events' action", m(ma, handle_response))
	
	-- wait for a response
	local time_string
	if expected_response then
		time_string = "half a second (500 milliseconds)"
		posix.usleep(500000)
	else
		time_string = "one second"
		posix.sleep(1)
	end

	-- check for a response
	check_err("manager error", m:pump_messages())
	m:process_responses()

	if not got_response and expected_response then
		fail("did not get a response to the 'Events' manager action in " .. time_string)
	elseif got_response and not expected_response then
		fail("got a response to the 'Events' manager action when we did not expect one:\n" .. got_response:_format())
	end
	
	m(action.logoff())
	m:close()
end

action = ast.manager.action

print("testing with brokeneventsaction off (default)")
standard = ast.new()
standard:generate_manager_conf()
standard:spawn()

test_events_response(standard, "", true)
test_events_response(standard, "ON", true)
test_events_response(standard, "yes", true)
test_events_response(standard, "all", true)
test_events_response(standard, "all,user", true)
test_events_response(standard, "system,user,agent", true)
test_events_response(standard, "off", true)
test_events_response(standard, "none", true)
test_events_response(standard, "yeah whatever", true)
test_events_response(standard, "1", true)

-- term or kill asterisk, ignoring any errors
proc.perror(standard:term_or_kill())

print("testing with brokeneventsaction on")
quirks = ast.new()
quirks:generate_manager_conf()
quirks["manager.conf"]["general"]["brokeneventsaction"] = "yes"
quirks:spawn()

test_events_response(quirks, "", false)
test_events_response(quirks, "ON", false)
test_events_response(quirks, "yes", false)
test_events_response(quirks, "all", false)
test_events_response(quirks, "all,user", false)
test_events_response(quirks, "system,user,agent", true)
test_events_response(quirks, "off", true)
test_events_response(quirks, "none", true)
test_events_response(quirks, "yeah whatever", true)
test_events_response(quirks, "1", true)

-- term or kill asterisk, ignoring any errors
proc.perror(quirks:term_or_kill())

