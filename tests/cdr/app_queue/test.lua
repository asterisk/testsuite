
require "cdr"

function mcheck(msg, r, err)
	check(msg, r, err)
	if r["Response"] ~= "Success" then
		error(msg .. ": " .. r["Message"])
	end
	return r
end

function sipp_exec(scenario, name, host, port)
	host = host or "127.0.0.1" 
	port = port or "5060"
	local inf = "data.csv"
	local p = proc.exec_io("sipp",
	"127.0.0.1",
	"-m", "1",
	"-sf", scenario,
	"-inf", "sipp/" .. inf,
	"-infindex", inf, "0",
	"-i", host,
	"-p", port,
	"-timeout", "30",
	"-timeout_error",
	"-set", "user", name,
	"-set", "file", inf
	)

	posix.sleep(1)
	return p
end

function sipp_exec_and_wait(scenario, name, host, port)
	return sipp_check_error(sipp_exec(scenario, name, host, port), scenario)
end

function sipp_check_error(p, scenario)
	local res, err = p:wait()	

	if not res then error(err) end
	if res ~= 0 then 
		error("error while executing " .. scenario .. " sipp scenario (sipp exited with status " .. res .. ")\n" .. p.stderr:read("*a"))
	end
	
	return res, err
end

function check_cdr_disposition(a, record, disposition)
	print("checking CDR")
	local c = check("error parsing cdr file", cdr.new(a))

	fail_if(not c[record], string.format("expected disposition '%s' in record %s, but file only has %s record(s)", disposition, record, c:len()))
	fail_if(c[record]["disposition"] ~= disposition, string.format("expected disposition '%s' in record %s, but found '%s'", disposition, record, tostring(c[record]["disposition"])))
end

function check_for_n_cdrs(a, records)
	local c, err = cdr.new(a)
	local c = check("error parsing cdr file", cdr.new(a))

	fail_if(c:len() ~= records, string.format("expected %s cdr(s) but found %s", records, c:len()))
end

function do_call(scenario, key)
	-- start sipp and wait for calls
	print(string.format("starting sipp (%s)", scenario))
	local s1 = check("error starting sipp", sipp_exec("sipp/" .. scenario, key, "127.0.0.2"))

	-- wait for everything to finish
	print("waiting for sipp to exit")
	sipp_check_error(s1, "sipp/" .. scenario)

	posix.sleep(1) -- give asterisk a second to write CDRs
end

function do_two_calls(scenario1, key1, scenario2, key2)
	-- start sipp and wait for calls
	print(string.format("starting first sipp (%s)", scenario1))
	local s1 = check("error starting sipp", sipp_exec("sipp/" .. scenario1, key1, "127.0.0.2"))

	print(string.format("starting second sipp (%s)", scenario2))
	local s2 = check("error starting sipp", sipp_exec("sipp/" .. scenario2, key2, "127.0.0.3"))

	-- wait for everything to finish
	print("waiting for sipp to exit")
	sipp_check_error(s2, "sipp/" .. scenario2)
	sipp_check_error(s1, "sipp/" .. scenario1)

	posix.sleep(1) -- give asterisk a second to write CDRs
end

-- start asterisk
print("starting asterisk")
a = ast.new()
a:load_config("configs/sip.conf")
a:load_config("configs/extensions.conf")
a:load_config("configs/cdr.conf")
a:load_config("configs/queues.conf")

if ast.has_major_version("1.4") then
	a:load_config("configs/modules.conf")
end

a:spawn()

-- make test calls

print("testing abandoned call")
do_call("call-then-hangup.xml", "abandon")
check_cdr_disposition(a, 1, "ANSWERED")
check_for_n_cdrs(a, 1)

print("testing normal agent completed call")
do_two_calls("wait-for-call-hangup.xml", "completeagent", "call.xml", "answered")
check_cdr_disposition(a, 2, "ANSWERED")
check_for_n_cdrs(a, 2)

print("testing call with joinempty=no and an empty queue")
do_call("call.xml", "exitempty")
check_cdr_disposition(a, 3, "ANSWERED")
check_for_n_cdrs(a, 3)

print("testing a timeout")
do_call("call.xml", "timeout")
check_cdr_disposition(a, 4, "ANSWERED")
check_for_n_cdrs(a, 4)

