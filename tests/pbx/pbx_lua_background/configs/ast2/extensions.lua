-- vim: sw=4 et:

extensions = {}
extensions.test = {}

extensions.test[1234] = function(c, e)
    app.answer()
    app.background("demo-congrats")

    -- this line should not execute because of the preceding background
    app.userevent("TestResult", "result: fail", "error: background didn't work")
end

extensions.test[12345] = function(c, e)
    app.userevent("TestResult", "result: pass")
end

