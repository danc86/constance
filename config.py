
# vim:encoding=utf-8

import os
from ConfigParser import SafeConfigParser

class ConstanceConfigParser(SafeConfigParser):

    def __init__(self, filename):
        SafeConfigParser.__init__(self)
        self.readfp(open(os.path.join(os.path.dirname(__file__), 'config.defaults'), 'r'))
        self.readfp(open(filename, 'r'))

    def getunicode(self, section, option):
        return self.get(section, option).decode('utf8') # XXX make codec configurable?
