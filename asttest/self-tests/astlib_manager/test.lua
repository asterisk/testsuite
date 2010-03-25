-- test spawning and connecting to asterisk

skip_if(not ast.exists(), "asterisk not found")

a = ast.new()
a:generate_manager_conf()

a:spawn()

m, err = a:manager_connect()
if not m then
	fail("error connecting to asterisk: " .. err)
end

action = ast.manager.action

r = m(action.login())
if not r then
	fail("error logging in to the manager: " .. err)
end

if r["Response"] ~= "Success" then
	fail("error authenticating: " .. r["Message"])
end

r = m(action.logoff())

status, err = a:term_or_kill()
if not status then
	fail("error terminating asterisk: " .. err)
end
print("asterisk exited with status: " .. status)

