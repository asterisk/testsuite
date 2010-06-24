--package.path = package.path .. ";lua/?.lua"
require "watcher"

-- test spawning and connecting to asterisk
a = ast.new()
a:generate_manager_conf()

a:spawn()

posix.sleep(1)

m, err = a:manager_connect()
if not m then
	fail("error connecting to asterisk: " .. err)
end

login = ast.manager.action:new("login")
login["Username"] = "asttest"
login["Secret"] = "asttest"

logoff = ast.manager.action:new("logoff")

r = m(login)
if not r then
	fail("error logging in to the manager: " .. err)
end

if r["Response"] ~= "Success" then
	fail("error authenticating: " .. r["Message"])
end

function watch_events_working(m, events, timeout)
	local i = 1
	local keep_waiting = true

	function handler(e)
		m:unregister_event(e["Event"], handler)
		i = i + 1
		keep_waiting = false
	end

	while events[i] do
		keep_waiting = true
		m:register_event(events[i], handler)
		print("Got event: " .. events[i] .. " " .. events[i][1])

		while keep_waiting do
			local res, err = m:wait_event()
			if not res then
				error("Error while waiting for event '" .. events[i] .. "': " .. err)
			end
			m:process_events()
		end
	end
end

    --for i=1,100000 do s = s + i end
   -- print(string.format("elapsed time: %.2f\n", os.clock() - x))

function watch_events(m, events, loops)
	local i = 1
	local keep_waiting = true
	local cur_loops = loops
	local logged = 1

	function handler(e)
		--print("Got event #" .. logged .. ": " .. events[i] .. e:_format())
		print("Got event #" .. logged .. ": " .. e:_format())
		logged = logged + 1
		m:unregister_event(e["Event"], handler)
		i = i + 1
		keep_waiting = false
		cur_loops = loops
	end

	while (events[i] and cur_loops > 0) do
		keep_waiting = true
		--m:register_event(events[i], handler)
		local j = 1
		while (events[j]) do
			m:register_event(events[j], handler)
			print("Registered event #" .. j .. ": " .. events[j])
			j = j + 1
		end

		while keep_waiting and cur_loops > 0 do
print("cur_loops " .. cur_loops)
			local res, err = m:pump_messages()
			if not res then
				error("Error while waiting for event '" .. events[i] .. "': " .. err)
			end
			m:process_events()
			a.ex_sleep(1)
			cur_loops = cur_loops - 1
		end
	end

	--if (keep_waiting == true) then
	if (cur_loops == 0) then
		print("Timed out waiting for events! ")
	end
end

function my_watch_events(m, events, timeout)
	a.ex_sleep(timeout);
end

--my_watch_events(m, {"Alarm", "Alarm"}, 1)
--watch_events(m, {"Alarm", "Alarm" ,"Alarm"}, 2)
--watch_events(m, {"Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm", "Alarm"}, 2)
--watch_events_working(m, {"Alarm", "Alarm"}, 10)

function myfunc(e)
	print(e:_format())
	print("")
--	for k,v,z in pairs(e) do 
--		print("aaa " .. k,v,z,e["Event"],e["Data"])
--		print("")
--	end
	return 1
end

--m:register_event("SpanAlarm", function(e) print("Got event: " .. e["Event"]) end)
--m:register_event("Alarm", function(e) print("Got event: " .. e["Event"]) end)
--m:register_event("Alarm", myfunc)
--m:wait_event()
--m:pump_messages()
--m:process_events()

e1 = watcher.event.new("Alarm")
e1["Alarm"] = "Red Alarm"
e2 = watcher.event.new("Alarm")
e3 = watcher.event.new("Alarm")

etree = watcher.etree:new(e1)
etree:add(e2):add(e1)
etree:add(e3)

print(tostring(etree))

res, err = watcher.watch(m, etree, 12000)

r = m(logoff)

if not res then
   fail("error waiting for events: " .. err)
end

status, err = a:term()
if not status then
	fail("error terminating asterisk: " .. err)
end

