-- vim: sw=4 et:

extensions = {}
extensions.test = {}

extensions.test[1234] = function(c, e)
    app.answer()
    app.goto("test", "12345", 1)

    -- this line should not execute because of the preceding goto
    app.userevent("TestResult", "result: fail", "error: goto didn't actually cause a goto")
end

extensions.test[12345] = function(c, e)
    app.userevent("TestResult", "result: pass")
end

