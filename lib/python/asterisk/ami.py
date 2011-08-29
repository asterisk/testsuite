from twisted.internet import reactor, protocol
from starpy import manager
import datetime
import sys
import logging

logger = logging.getLogger(__name__)

class AMI:
    def __init__(self, on_login, on_error, timeout=60, user="mark", secret="mysecret", host="127.0.0.1", port=5038):
        self.on_login = on_login
        self.on_error = on_error
        self.login_timeout = timeout
        self.user = user
        self.secret = secret
        self.host = host
        self.port = port
        self.__attempts = 0
        self.__start = None
        self.ami_factory = manager.AMIFactory(self.user, self.secret)

    def login(self):
        self.__attempts = self.__attempts + 1
        logger.debug("AMI Login attempt #%d" % (self.__attempts))
        if not self.__start:
            self.__start = datetime.datetime.now()
        self.ami_factory.login(self.host, self.port).addCallbacks(self.on_login_success, self.on_login_error)

    def on_login_success(self, ami):
        self.ami = ami
        logger.debug("AMI Login succesful")
        return self.on_login(ami)

    def on_login_error(self, reason):
        runtime = (datetime.datetime.now() - self.__start).seconds
        if runtime >= self.login_timeout:
            logger.error("AMI login failed after %d second timeout" % (self.login_timeout))
            return self.on_error()
        delay = 2 ** self.__attempts
        if delay + runtime >= self.login_timeout:
            delay = self.login_timeout - runtime
        reactor.callLater(delay, self.login)

