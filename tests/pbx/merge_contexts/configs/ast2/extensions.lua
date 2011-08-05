-- vim: sw=4 et:

extensions = {}
extensions.test = {}

extensions.test[1234] = function(c, e)
    app.answer()
    app.userevent("TestResult", "result: pass")
end

