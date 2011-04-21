have_error = false
function print_error(err)
	print(err)
	have_error = true
end

function sipp_exec(to, from)
	return proc.exec_io("sipp",
	to,
	"-m", "1",
	"-t", "t1",
	"-sn", "uac",
	"-d", 10000,      -- keep calls up for 10 seconds
	"-i", from,
	"-p", 5060,
	"-timeout", "60",
	"-timeout_error"
	)
end

function sipp_check_error(p, index)
	local res, err = p:wait()

	if not res then
		print_error(err)
		return res, err
	end
	if res ~= 0 then
		print_error("error while connecting client " .. index .. " (sipp exited with status " .. res .. ")\n" .. p.stderr:read("*a"))
	end

	return res, err
end

function connect(addr)
	local sock, err = socket.tcp()
	if not sock then
		return nil, err
	end

	local res, err = sock:connect(addr, 5060)
	if not res then
		sock:close()
		return nil, err
	end

	-- select then read from the sock to see if it is sill up
	local read, _, err = socket.select({sock}, nil, 0.1)
	if read[1] ~= sock and err ~= "timeout" then
		return nil, err
	end

	-- if we have data, then there is probably a problem because chan_sip
	-- doesn't send anything to new sockets
	if read[1] == sock then
		res, err = sock:receive(1);
		if not res then
			return nil, err
		end
	end

	return sock
end

-- limit chan_sip to 5 connections
limit = 5

print("starting asterisk")
a = ast.new()
a["sip.conf"]["general"]["tcpauthlimit"] = limit
a["sip.conf"]["general"]["tcpenable"] = "yes"
sip_addr = "127.0.0." .. a.index
a["sip.conf"]["general"]["tcpbindaddr"] = sip_addr

a["extensions.conf"]["default"]["exten"] = "service,1,Answer"
a["extensions.conf"]["default"]["exten"] = "service,n,Wait(60)"
a:spawn()

clients = {}

print("connecting " .. limit .. " clients to asterisk")
for i = 1, limit do
	local sock = check("error connecting to chan_sip via TCP", connect(sip_addr))
	table.insert(clients, sock)
end

print("attempting to connect one more, this should fail")
fail_if(connect(sip_addr), "client " .. limit + 1 .. " successfully connected, this should have failed")

for _, sock in ipairs(clients) do
	sock:shutdown("both")
	sock:close()
end

posix.sleep(3) -- let the connections shut down

print("connecting and authenticating " .. limit * 2 .. " clients to asterisk")
clients = {}
for i = 1, limit * 2 do
	table.insert(clients, sipp_exec(sip_addr, "127.0.0." .. a.index + i))

	-- for some reason sipp opens two connections to asterisk when setting
	-- up a call.  Pausing here gives time for one of them to go away.
	posix.sleep(1)
end

print("checking for errors")
for i, sipp in ipairs(clients) do
	sipp_check_error(sipp, i)
end

fail_if(have_error, "one (or more) of our clients had a problem")

