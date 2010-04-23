srv_record = {}
function srv_record:new(host, port, priority, weight)
	local s = {
		host = host or '',
		port = port or 0,
		priority = priority or 0,
		weight = weight or 0
	}
	setmetatable(s, self)
	self.__index = self
	return s
end

function srv_record.__eq(rec1, rec2)
	-- Helpful for debugging
	print ("Going to compare the following:")
	print ("Host 1: " .. rec1.host .. " Host 2: " .. rec2.host)
	print ("Port 1: " .. rec1.port .. " Port 2: " .. rec2.port)
	print ("priority 1: " .. rec1.priority .. " priority 2: " .. rec2.priority)
	print ("weight 1: " .. rec1.weight .. " weight 2: " .. rec2.weight)
	return rec1.host == rec2.host and rec1.port == rec2.port and rec1.priority == rec2.priority and rec1.weight == rec2.weight
end

srv_records = {
	srv_record:new("udpserver1.asteriskcheck.com","5060","0","3"),
	srv_record:new("udpserver2.asteriskcheck.com","5061","1","0"),
	srv_record:new("udpserver3.asteriskcheck.com","5060","1","0"),
	srv_record:new("udpserver4.asteriskcheck.com","5060","65535","65535")
}

function analyze_srv(event)
	local record_num = tonumber(event["RecordNum"])
	local record = srv_record:new(event["Host"], event["Port"], event["Priority"], event["Weight"])
	--Helpful for debugging
	print ("User event callback")
	print ("Got record Host: " .. event["Host"] .. " Port: " .. event["Port"] .. " Priority: " .. event["Priority"] .. " Weight: " .. event["Weight"])
	if record ~= srv_records[record_num] then
		-- Since records 2 and 3 share the same priority, it is unpredictable
		-- which order we'll see them arrive
		if record_num == 2 then
			record_num = 3
		elseif record_num == 3 then
			record_num = 2
		else
			fail("Records don't match!")
		end
		if record ~= srv_records[record_num] then
			fail("Records don't match!")
		end
	end
end

function do_call(man, exten)
	local orig = ast.manager.action:new("Originate")
	orig["Channel"] = "Local/" .. exten .. "@test_context"
	orig["Application"] = "Wait"
	orig["Data"] = "3"
	man:register_event("UserEvent", analyze_srv)
	local res, err = man(orig)
	if not res then
		fail("Error originating call: " .. err)
	end
	if res["Response"] ~= "Success" then
		fail("Response failure for Originate: " .. res["Message"])
	end
	posix.sleep(4)
	res, err = man:pump_messages()
	if not res then
		fail("Error pumping messages: " .. err)
	end
	man:process_events()
	man:unregister_event("UserEvent", analyze_srv)
end

instance = ast.new()
instance:load_config("configs/extensions.conf")
instance:generate_manager_conf()
instance:spawn()

man,err = instance:manager_connect()
if not man then
	fail("error connecting to asterisk: " .. err)
end

login = ast.manager.action.login()
if not login then
	fail("Couldn't create login?")
end
man(login)
do_call(man, "test")
do_call(man, "test2")
logoff = ast.manager.action.logoff()
man(logoff)
instance:term_or_kill()
