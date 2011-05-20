require "watcher"

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

function mcheck(msg, res, err)
	check(msg, res, err)
	if res["Response"] ~= "Success" then
		error(msg .. " (got '" .. tostring(res["Response"]) .. "' expected 'Success'): " .. tostring(res["Message"]))
	end
	return res, err
end

function wait_for_event(m, result)
	local e = watcher.event.new("UserEvent")
	e["UserEvent"] = "TransferComplete"
	e["TRANSFERSTATUS"] = function(value)
		if result ~= value then
			print("Got '" .. value .. "' for TRANSFERSTATUS, expected '" .. result .. "'")
			return false
		end
		return true
	end
	local etree = watcher.etree:new(e)

	local res, err = check("error waiting for UserEvent", watcher.watch(m, etree, 10000))
end

function do_call(scenario, key, result)
	local action = ast.manager.action

	local a = ast.new()
	a:load_config("configs/ast1/sip.conf")
	a:load_config("configs/ast1/extensions.conf")
	a:generate_manager_conf()
	a:spawn()

	local m = a:manager_connect()
	mcheck("error logging into manager", m(action.login()))

	local t1 = sipp_exec(scenario, key, "127.0.0.2")

	local o = action.new("Originate")
	o["Channel"] = "sip/test1@127.0.0.2"
	o["Context"] = "transfer"
	o["Exten"] = "s"
	o["Priority"] = 1

	mcheck("error originating call", m(o))
	wait_for_event(m, result)
	sipp_check_error(t1, scenario)

	proc.perror(a:term_or_kill())
end

tests = {
	-- {description,
	-- 	scenario,
	-- 	resp key, TRANSFERSTATUS}

	{"Testing response 202",
		"sipp/wait-refer-202-notify.xml",
		"202", "SUCCESS"},

	{"Testing response 202 with a provisional response",
		"sipp/wait-refer-202-notify-provisional.xml",
		"202", "SUCCESS"},

	{"Testing response 200",
		"sipp/wait-refer-200-notify.xml",
		"200", "FAILURE"},

	{"Testing response 202 followed by a 603 notify",
		"sipp/wait-refer-202-notify.xml",
		"202-603", "FAILURE"},

	{"Testing response 202 followed by a 603 notify with a provisional resposne",
		"sipp/wait-refer-202-notify-provisional.xml",
		"202-603", "FAILURE"},

	{"Testing response 202 followed by a 500 notify",
		"sipp/wait-refer-202-notify.xml",
		"202-500", "FAILURE"},

	{"Testing response 400",
		"sipp/wait-refer-400.xml",
		"400", "FAILURE"},

	{"Testing response 500",
		"sipp/wait-refer-500.xml",
		"500", "FAILURE"},

	{"Testing response 603",
		"sipp/wait-refer-603.xml",
		"603", "FAILURE"},

	{"Testing response 202 with buggy notify",
		"sipp/wait-refer-202-error.xml",
		"202-err", "FAILURE"},
}

for _, t in ipairs(tests) do
	print(t[1])
	do_call(t[2], t[3], t[4])
end

