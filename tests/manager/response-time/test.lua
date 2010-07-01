function check(msg, r, err)
	if not r then
		error(msg .. ": " .. tostring(err))
	end
	return r
end

function timed_action(m, a, r)
	local start = posix.gettimeofday()
	local res, err = m(a)
	local stop = posix.gettimeofday()

	if a["Action"] ~= "Logoff" and not res then
		error(string.format("Error sending action '%s': %s", a["Action"], tostring(err)))
	end

	if r then
		r(res, err)
	end

	-- return the total number of usecs
	return (stop.tv_sec - start.tv_sec) * 1000000 + (stop.tv_usec - start.tv_usec)
end

function test_action(results, m, a, r)
	for i=1,10 do
		table.insert(results, {timed_action(m, a, r), a["Action"]})
	end
end

function mean(results)
	if #results == 0 then
		return 0
	end

	local total = 0
	for _, val in ipairs(results) do
		total = total + val[1]
	end
	return total / #results
end

function print_results(results)
	for _, val in ipairs(times) do
		print(val[2] .. ": " .. val[1])
	end
end

action = ast.manager.action

print("starting asterisk")
asterisk = ast.new()
asterisk:generate_manager_conf()
asterisk:spawn()

m = check("error connecting to asterisk", asterisk:manager_connect())

print("testing login")
times = {}
table.insert(times, {timed_action(m, action.login(), function(res, err)
	if res["Response"] ~= "Success" then
		error("error authenticating: " .. res["Message"])
	end
end), "Login"})

print("testing ping")
test_action(times, m, action.ping())

print("testing logoff")
table.insert(times, {timed_action(m, action.logoff()), "Logoff"})

avg = mean(times)
print("average time per response was " .. avg .. " usecs")

-- there is a problem if the average time is greater than 5000 usecs 5000 was
-- chosen after running this test multiple times on my system while compiling
-- asterisk with make -j4.  During this an previous runs the average time never
-- went over 3000.  During failed runs, the average time is around 35000; so
-- 5000 should prevent any false positives while still detecting failures.
-- Really average times should be less than 500, but system load cause them to
-- spike.
expected_avg = 5000
if avg > expected_avg then
	print("average time greater than " .. expected_avg .. " usec")
	print("recorded time per action:")
	print_results(times)
	fail("manager took too long to respond; average time was " .. avg .. " usecs")
end

-- there is also a problem if any of the individual times were over 5000
-- once again, individual times should really be less than 250 usec, but system
-- load can cause this to spike.
individual_time = 5000
for _, val in ipairs(times) do
	if val[1] > individual_time then
		print(string.format("time for action '%s' was greater than %s usecs", val[2], individual_time))
		print("all times:")
		print_results(times)
		fail(string.format("action '%s' took longer than %s usecs", val[2], individual_time))
	end
end

