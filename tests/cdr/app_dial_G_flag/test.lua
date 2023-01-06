require "cdr"

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

function sipp_check_error(p, scenario)
	local res, err = proc.perror(p:wait())

	if not res then error(err) end
	if res ~= 0 then
		error("error while executing " .. scenario .. " sipp scenario (sipp exited with status " .. res .. ")\n" .. p.stderr:read("*a"))
	end

	return res, err
end

-- start asterisk
print("starting asterisk")
a = ast.new()
a:load_config("configs/ast1/extensions.conf")
a:load_config("configs/ast1/pjsip.conf")
a:generate_manager_conf()
a:spawn()

s1 = check("error starting sipp", sipp_exec("sipp/wait-for-call.xml", "test1", "127.0.0.2"))
s2 = check("error starting sipp", sipp_exec("sipp/call.xml", "test2", "127.0.0.3"))

sipp_check_error(s1, "wait-for-call.xml")
sipp_check_error(s2, "call.xml")

c = check("error loding cdr", cdr.new(a))
fail_if(c:len() ~= 2, "expected 2 cdr records, found " .. c:len())

