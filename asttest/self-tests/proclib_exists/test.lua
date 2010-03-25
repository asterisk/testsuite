-- test proclib's ablity to detect missing and non-executable files


-- this function expects the give path to exist
function should_succeed(path)
	local res, err = proc.exists(path)
	if not res then
		fail("error detecting '" .. path .. "': " .. err)
	end
end

-- this function expects the given path to NOT exist
function should_fail(path)
	local res, err = proc.exists(path)
	if res then
		fail("falsely detected '" .. path .. "'")
	end
end

should_succeed("echo")
should_succeed("/bin/echo")
should_succeed("/bin/sh")

should_fail("this file won't exist, except for under extreme circumstances")
should_fail("/same for this one")
should_fail("")

should_fail("/tmp")
should_fail("/var/log/syslog")

