-- test asterisk version string parsing

function normal_version(version, concept, major, minor, patch)
	print("testing " .. version)
	local v = ast.version(version)
	fail_if(v.svn, version .. " was detected as an svn version")
	fail_if(tostring(v) ~= version, string.format("tostring(v) for %s ~= %s", version, version))
	fail_if(v.concept ~= concept, string.format("v.concept ~= concept (%s ~= %s)", v.concept or "nil", concept or "nil"))
	fail_if(v.major ~= major, string.format("v.major ~= major (%s ~= %s)", v.major or "nil", major or "nil"))
	fail_if(v.minor ~= minor, string.format("v.minor ~= minor (%s ~= %s)", v.minor or "nil", minor or "nil"))
	fail_if(v.patch ~= patch, string.format("v.patch ~= patch (%s ~= %s)", v.patch or "nil", patch or "nil"))
end

function synthetic_version(version, concept, major, minor, patch)
	print("testing synthetic " .. version)
	local v = ast.version(version)
	fail_if(not v.svn, version .. " was NOT detected as an svn version")
	fail_if(tostring(v) ~= version, string.format("tostring(v) for %s ~= %s", version, version))
	fail_if(v.concept ~= concept, string.format("v.concept ~= concept (%s ~= %s)", v.concept or "nil", concept or "nil"))
	fail_if(v.major ~= major, string.format("v.major ~= major (%s ~= %s)", v.major or "nil", major or "nil"))
	fail_if(v.minor ~= minor, string.format("v.minor ~= minor (%s ~= %s)", v.minor or "nil", minor or "nil"))
	fail_if(v.patch ~= patch, string.format("v.patch ~= patch (%s ~= %s)", v.patch or "nil", patch or "nil"))
end

function svn_version(version, branch, revision, parent)
	print("testing svn " .. version)
	local v = ast.version(version)
	fail_if(not v.svn, version .. " was NOT detected as an svn version")
	fail_if(tostring(v) ~= version, string.format("tostring(v) for %s ~= %s", version, version))
	fail_if(v.branch ~= branch, string.format("v.branch ~= branch (%s ~= %s)", v.branch or "nil", branch or "nil"))
	fail_if(v.revision ~= revision, string.format("v.revision ~= revision (%s ~= %s)", v.revision or "nil", revision or "nil"))
	fail_if(v.parent ~= parent, string.format("v.parent ~= parent (%s ~= %s)", v.parent or "nil", parent or "nil"))
end

function synthetic_svn_version(version, branch, revision)
	print("testing synthetic svn " .. version)
	local v = ast.version(version)
	fail_if(v.svn, version .. " was detected as an svn version")
	fail_if(tostring(v) ~= version, string.format("tostring(v) for %s ~= %s", version, version))
	fail_if(v.branch ~= branch, string.format("v.branch ~= branch (%s ~= %s)", v.branch or "nil", branch or "nil"))
	fail_if(v.revision ~= revision, string.format("v.revision ~= revision (%s ~= %s)", v.revision or "nil", revision or "nil"))
end

function major_version(v1, v2)
	print(string.format("testing major version %s matches %s", v1, v2))
	local old_version = ast._version
	ast._version = function()
		return v2
	end

	fail_if(not ast.has_major_version(v1), string.format("ast.has_major_version(%s) failed for %s", v1, v2))

	ast._version = old_version
end

function not_major_version(v1, v2)
	print(string.format("testing major version %s does not match %s", v1, v2))
	local old_version = ast._version
	ast._version = function()
		return v2
	end

	fail_if(ast.has_major_version(v1), string.format("ast.has_major_version(%s) matched for %s", v1, v2))

	ast._version = old_version
end

function compare_false(str)
	local left, cmp, right = str:match("^([^%s]+) ([>=<~]+) ([^%s]+)$")
	if not left then
		error(string.format("invalid comparison string '%s'", str))
	end

	local chunk_str = string.format("return ast.version(\"%s\") %s ast.version(\"%s\")", left, cmp, right)
	local chunk, err = loadstring(chunk_str, "compairson")
	if not chunk then
		error(string.format("error building compairson for '%s' (%s): %s", str, chunk_str, err))
	end

	fail_if(chunk(), string.format("%s was true, should have been false (%s)", str, chunk_str))
end

function compare(str)
	local left, cmp, right = str:match("^([^%s]+) ([>=<~]+) ([^%s]+)$")
	if not left then
		error(string.format("invalid comparison string '%s'", str))
	end

	local chunk_str = string.format("return not (ast.version(\"%s\") %s ast.version(\"%s\"))", left, cmp, right)
	local chunk, err = loadstring(chunk_str, "comparison")
	if not chunk then
		error(string.format("error building compairson for '%s' (%s): %s", str, chunk_str, err))
	end

	fail_if(chunk(), string.format("%s failed (%s)", str, chunk_str))
end

normal_version("1.4.30", "1", "4", "30")
normal_version("1.4.30.1", "1", "4", "30", "1")
normal_version("1.4", "1", "4")
normal_version("C.3", "C", "3")
normal_version("C.3.5", "C", "3", "5")
normal_version("10", "10")
normal_version("10.0", "10", "0")
normal_version("10.0.1", "10", "0", "1")
synthetic_svn_version("1.4.30", "branch-1.4", "00000")
synthetic_svn_version("1.4.30.1", "branch-1.4", "00000")
synthetic_svn_version("1.4", "branch-1.4", "00000")
synthetic_svn_version("C.3", "branch-C.3", "00000")
synthetic_svn_version("C.3.5", "branch-C.3", "00000")
synthetic_svn_version("C.3", "branch-C.3", "00000")
synthetic_svn_version("10", "branch-10", "00000")
synthetic_svn_version("10.0", "branch-10", "00000")
synthetic_svn_version("10.0.1", "branch-10", "00000")

svn_version("SVN-trunk-r252849", "trunk", "252849")
svn_version("SVN-branch-1.6.2-r245581M", "branch-1.6.2", "245581M")
svn_version("SVN-branch-C.3-r1234", "branch-C.3", "1234")
svn_version("SVN-branch-10-r1234", "branch-10", "1234")
svn_version("SVN-branch-C.3-duckpond-r1234", "branch-C.3-duckpond", "1234")
svn_version("SVN-russell-cdr-q-r249059M-/trunk", "russell-cdr-q", "249059M", "/trunk")
svn_version("SVN-russell-rest-r1234", "russell-rest", "1234")
synthetic_version("SVN-trunk-r252849", "999", "0", "0", "252849")
synthetic_version("SVN-branch-1.6.2-r245581M", "1", "6", "2", "245581")
synthetic_version("SVN-branch-10-r245581M", "10", "245581")
synthetic_version("SVN-russell-cdr-q-r249059M-/trunk", "998", "0", "0", "249059")
synthetic_version("SVN-russell-rest-r1234", "998", "0", "0", "1234")
synthetic_version("SVN-branch-1.4-r1234", "1", "4", "999", "1234")
synthetic_version("SVN-branch-C.3-r1234", "C", "3", "998", "1234")
synthetic_version("SVN-branch-C.3-duckpond-r1234", "C", "3", "999", "1234")

major_version("1.4", "1.4.30")
major_version("1.4", "1.4.30.1")
major_version("trunk", "SVN-trunk-r224353")
major_version("1.4", "SVN-branch-1.4-r224353")
major_version("1.6.2", "SVN-branch-1.6.2-r224353")
major_version("1.6.2", "1.6.2.0")
major_version("C.3", "C.3")
major_version("C.3", "C.3.5")
major_version("10", "10.0")

not_major_version("1.4", "1.6.2")
not_major_version("1.4", "1.8")
not_major_version("1.6", "SVN-trunk-r224353")
not_major_version("1.6.1", "1.6.2")
not_major_version("trunk", "1.6.2")
not_major_version("trunk", "C.3")
not_major_version("C.3", "1.4.3")

print("testing comparisons")

-- these comparisons should evaluate to false
compare_false("1.6 > 1.6.2")
compare_false("1.6 == 1.6.2")
compare_false("1.6.2 > 1.6.2")
compare_false("1.6.2 < 1.6.2")
compare_false("1.6.2 ~= 1.6.2")
compare_false("1.6.2 >= 1.6.3")

-- these comparisons should evaluate to true
compare("10 > 1.6.2")
compare("10.0 > 1.6.2")
compare("1.6.2 <= 1.6.2")
compare("1.6.2 <= 1.6.3")
compare("1.4 < 1.6.2")
compare("1.4 < 1.4.2")
compare("1.4.30 < 1.6")
compare("1.4.30 < SVN-branch-1.6.2-r224353")
compare("1.4.30 < SVN-branch-1.4-r224353")
compare("SVN-branch-1.6.2-r224353 == SVN-branch-1.6.2-r224353")
compare("SVN-branch-1.6.2-r224352 < SVN-branch-1.6.2-r224353")
compare("SVN-trunk-r1234 > SVN-branch-1.6.2-r224353")
compare("C.3 < 1.6.2")
compare("C.3 > 1.4.34")
compare("C.3.6 > 1.4.34")
compare("C.3.6.2 > 1.4.34")
compare("C.3.6.2 > C.3")
compare("C.3.6.2 > C.3.6")

if ast.exists() then
	print("automatically detected version " .. tostring(ast.version()))
end

