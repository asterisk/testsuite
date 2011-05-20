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
	"-d", timeout * 2,   -- keep calls up longer than the timeout
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

	return check_sock(sock)
end

function check_sock(sock)
	-- select then read from the sock to see if it is still up
	local read, _, err = socket.select({sock}, nil, 0.1)
	if read[1] ~= sock and err ~= "timeout" then
		return nil, err
	end

	-- if we have data, then there is probably a problem because chan_sip
	-- doesn't send anything to new sockets
	if read[1] == sock then
		local res, err = sock:receive(1);
		if not res then
			return nil, err
		end
	end

	return sock
end

function write_sock(sock, data)
	local res, err, i = nil, nil, 0

	while i < #data do
		res, err, i = sock:send(data, i)
		if err then
			return nil, err
		else
			i = res
		end
	end
	return true
end

-- timeout connections after 5 seconds
timeout = 5

print("starting asterisk")
a = ast.new()
a["sip.conf"]["general"]["tcpauthtimeout"] = timeout
a["sip.conf"]["general"]["tcpenable"] = "yes"
sip_addr = "127.0.0." .. a.index
sip_port = "5060"
a["sip.conf"]["general"]["tcpbindaddr"] = sip_addr .. ":" .. sip_port

a["extensions.conf"]["default"]["exten"] = "service,1,Answer"
a["extensions.conf"]["default"]["exten"] = "service,n,Wait(60)"
a:spawn()

print("testing timeout of an unauthenticated session")
sock = check("error connecting to asterisk via TCP", connect(sip_addr))
posix.sleep(timeout + 1);
fail_if(check_sock(sock), "asterisk did not close the connection after " .. timeout .. " seconds")

print("testing timeout of an unauthenticated session after writing some data")
sock = check("error connecting to asterisk via TCP", connect(sip_addr))
check("error writing data to the socket", write_sock(sock, "hi, this is your tester standby"))
posix.sleep(timeout + 1);
fail_if(check_sock(sock), "asterisk did not close the connection after " .. timeout .. " seconds")

print("testing timeout of an unauthenticated session after writing some different data")
sock = check("error connecting to asterisk via TCP", connect(sip_addr))
check("error writing data to the socket", write_sock(sock, "INVITE sip:service@127.0.0.1:5060 SIP/2.0\r\n"))
posix.sleep(timeout + 1);
fail_if(check_sock(sock), "asterisk did not close the connection after " .. timeout .. " seconds")

print("testing timeout of an unauthenticated session after writing data in bursts")
sock = check("error connecting to asterisk via TCP", connect(sip_addr))
check("error writing data to the socket", write_sock(sock, "hi, this is your tester standby\r\n"))
posix.sleep(1)
check("error writing data to the socket", write_sock(sock, "hi, this is your tester, again... standby"))
posix.sleep(1)
check("error writing data to the socket", write_sock(sock, "guess who?! yup, your tester... standby\r\n"))
posix.sleep(timeout);
fail_if(check_sock(sock), "asterisk did not close the connection after " .. timeout .. " seconds")

print("testing timeout of an authenticated session (should not timeout)")
sipp = sipp_exec(sip_addr, "127.0.0." .. a.index + 1)
sipp_check_error(sipp, 1)
fail_if(have_error, "our authenticated client a problem")

