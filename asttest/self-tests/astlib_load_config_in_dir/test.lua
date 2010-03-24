-- test astlib

skip_if(not ast.exists(), "asterisk not found")

-- generate what we expect to see
expected_test_conf = [[
[test]
test = 1
test = test
value = this
allow = true

]]

f = io.open("dir/expected_test.conf", "w")
f:write(expected_test_conf)
f:close()


-- load what we just wrote
a = ast.new()
a:load_config("dir/expected_test.conf")
a:spawn()
a:term_or_kill()

test_conf_path = a.work_area .. "/etc/asterisk/expected_test.conf"

f = io.open(test_conf_path)
test_conf = f:read("*a")
f:close()

-- diff the two
os.execute("diff -u dir/expected_test.conf " .. test_conf_path .. " > diff")

f = io.open("diff")
diff = f:read("*a")
f:close()

-- cleanup
os.execute("rm -f " .. test_conf_path .. " dir/expected_test.conf diff")

-- check if our two configs match
fail_if(test_conf ~= expected_test_conf, "test_conf does not match expected_test_conf\n\n" .. diff)

