
function check(msg, r, err)
	if not r then
		error(msg .. ": " .. err)
	end
	return r
end

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

function check_cdr(a, record, disposition)
	local cdr_path = a:path("/var/log/asterisk/cdr-csv/Master.csv")
	local f, err = io.open(cdr_path, "r")
	if not f then
		error("error opening cdr file (" .. cdr_path .. "): " .. err)
	end

	local found = false
	local lineno = 0
	for line in f:lines() do
		lineno = lineno + 1

		if lineno == record then
			fail_if(not line:find(string.format('"%s"', disposition)), string.format("did not find disposition '%s' on line %s of cdr:\n%s", disposition, lineno, line))
			found = true
			break
		end
	end
	fail_if(not found, string.format("expected disposition '%s' on line %s of cdr, but line %s does not exist in the file", disposition, record, record))
end

function check_for_n_cdrs(a, records)
	local cdr_path = a:path("/var/log/asterisk/cdr-csv/Master.csv")
	local f, err = io.open(cdr_path, "r")
	if not f then
		error("error opening cdr file (" .. cdr_path .. "): " .. err)
	end

	local found = false
	local lineno = 0
	for line in f:lines() do
		lineno = lineno + 1
	end
	fail_if(lineno ~= records, string.format("expected %s CDR(s) but found %s", records, lineno))
end

function do_originate(a, scenario, record, disposition, timeout, exten)
	local action = ast.manager.action
	
	-- start sipp and wait for calls
	print(string.format("starting sipp (%s)", scenario))
	local s1 = check("error starting sipp", sipp_exec("sipp/" .. scenario, "test1", "127.0.0.2"))

	-- send a call
	print("sending originate")
	local m = check("error connecting to asterisk", a:manager_connect())
	mcheck("error authenticating", m(action.login()))

	local originate = action.new("Originate")
	originate["Channel"] = "sip/test1"
	originate["Context"] = "default"
	originate["Exten"] = exten or "wait"
	originate["Priority"] = 1
	if timeout then originate["Timeout"] = timeout end
	check("error sending call", m(originate))

	-- wait for everything to finish
	print("waiting for sipp to exit")
	sipp_check_error(s1, "sipp/" .. scenario)

	m(action.logoff())
	m:disconnect()

	-- check and make sure the proper CDRs were generated
	posix.sleep(1) -- give asterisk a second to write CDRs
	print("checking CDR")
	check_cdr(a, record, disposition)
end

function do_originate_with_dial(a, record, disposition)
	local scenario = "wait-for-call-timeout.xml"
	print(string.format("starting sipp (%s)", scenario))
	local s1 = check("error starting sipp", sipp_exec("sipp/" .. scenario, "test2", "127.0.0.3"))

	do_originate(a, "wait-for-call.xml", record, disposition, nil, "dial")

	print("waiting for sipp to exit")
	sipp_check_error(s1, "sipp/" .. scenario)
end

-- start asterisk
print("starting asterisk")
a = ast.new()
a:load_config("configs/sip.conf")
a:load_config("configs/extensions.conf")
a:load_config("configs/cdr.conf")
a:generate_manager_conf()
a:spawn()

do_originate(a, "wait-for-call.xml", 1, "ANSWERED")
check_for_n_cdrs(a, 1)

do_originate(a, "wait-for-call-busy.xml", 2, "BUSY")
check_for_n_cdrs(a, 2)

do_originate(a, "wait-for-call-congestion.xml", 3, "FAILED")
check_for_n_cdrs(a, 3)

do_originate(a, "wait-for-call-timeout.xml", 4, "NO ANSWER", 1000)
check_for_n_cdrs(a, 4)

do_originate_with_dial(a, 5, "NO ANSWER")
check_for_n_cdrs(a, 5)

