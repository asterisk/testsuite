-- test astlib

skip_if(not ast.exists(), "asterisk not found")

-- generate what we expect to see
expected_test_conf = [[
[test]
test = 1
test = test
value = this
allow = true

[section]
value = yes
setting = on
ip = 10.10.10.10

[section]
value = no

#include file

[template](!)
value = default

[inherit](template)
value = default

[inherit](template,test)
value = default

[inherit_template](!,template,test)
value = default

]]

f = io.open("expected_test.conf", "w")
f:write(expected_test_conf)
f:close()


-- generate a config
a = ast.new()

a["test.conf"]["test"]["test"] = 1
a["test.conf"]["test"]["test"] = "test"
a["test.conf"]["test"]["value"] = "this"
a["test.conf"]["test"]["allow"] = true

a["test.conf"]["section"]["value"] = "yes"
a["test.conf"]["section"]["setting"] = "on"
a["test.conf"]["section"]["ip"] = "10.10.10.10"

s = a["test.conf"]:new_section("section")
s["value"] = "no"

a["test.conf"]:verbatim("#include file\n\n")

a["test.conf"]["template"].template = true
a["test.conf"]["template"]["value"] = "default"

a["test.conf"]["inherit"].inherit = {"template"}
a["test.conf"]["inherit"]["value"] = "default"

s = a["test.conf"]:new_section("inherit")
s.inherit = {"template", "test"}
s["value"] = "default"

a["test.conf"]["inherit_template"].template = true
a["test.conf"]["inherit_template"].inherit = {"template", "test"}
a["test.conf"]["inherit_template"]["value"] = "default"

a:spawn()
a:term_or_kill()

f = io.open(a:path("/etc/asterisk/test.conf"))
test_conf = f:read("*a")
f:close()

-- diff the two
os.execute("diff -u expected_test.conf " .. a:path("/etc/asterisk/test.conf") .. " > diff")

f = io.open("diff")
diff = f:read("*a")
f:close()

-- cleanup
os.execute("rm -f test.conf expected_test.conf diff")

-- check if our two configs match
fail_if(test_conf ~= expected_test_conf, "test_conf does not match expected_test_conf\n\n" .. diff)

