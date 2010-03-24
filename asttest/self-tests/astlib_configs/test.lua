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
c = ast.config:new("test.conf")
s = c:new_section("test")
s["test"] = 1
s["test"] = "test"
s["value"] = "this"
s["allow"] = true

s = c:new_section("section")
s["value"] = "yes"
s["setting"] = "on"
s["ip"] = "10.10.10.10"

s = c:new_section("section")
s["value"] = "no"

c:verbatim("#include file\n\n")

s = c:new_section("template")
s.template = true
s["value"] = "default"

s = c:new_section("inherit")
s.inherit = {"template"}
s["value"] = "default"

s = c:new_section("inherit")
s.inherit = {"template", "test"}
s["value"] = "default"

s = c:new_section("inherit_template")
s.template = true
s.inherit = {"template", "test"}
s["value"] = "default"

c:_write()

f = io.open("test.conf")
test_conf = f:read("*a")
f:close()

-- diff the two
os.execute("diff -u expected_test.conf test.conf > diff")

f = io.open("diff")
diff = f:read("*a")
f:close()

-- cleanup
os.execute("rm -f test.conf expected_test.conf diff")

-- check if our two configs match
fail_if(test_conf ~= expected_test_conf, "test_conf does not match expected_test_conf\n\n" .. diff)

