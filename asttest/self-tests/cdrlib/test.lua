
require "cdr"

-- imitate an asterisk object and the asterisk:path() function
function a(file)
	local a = {}
	function a:path()
		return file
	end
	return a
end

function check_record(c, record, field, value)
	fail_if(c[record][field] ~= value, ("%s of record %s is '%s' instead of '%s'"):format(field, record, tostring(c[record][field]), tostring(value)))
end

print("parsing a known good csv file")
c, err = cdr.new(a("good.csv"))
fail_if(not c, "failed to parse known good csv file, good.csv: " .. tostring(err))

fail_if(c:len() ~= 5, "cdr file contains 5 records, but the parser found " .. c:len() .. " records")
check_record(c, 1, "disposition", "ANSWERED")
check_record(c, 2, "billsec", "7")

print("parsing a csv file with errors")
c, err = cdr.new(a("buggy.csv"))
fail_if(c, "successfully parsed known buggy csv file, buggy.csv.  This should have failed.")

print("attempting to parse a non existent file")
c, err = cdr.new(a("does not exits.csv"))
fail_if(c, "successfully parsed non existent file???")

fail_if(ast.cdr ~= cdr, "ast.cdr ~= cdr, the cdr lib is not properly being inserted into the ast lib")

