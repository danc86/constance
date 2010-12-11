#!/usr/bin/env python
# vim:encoding=utf-8

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

from ConfigParser import SafeConfigParser
import re
import datetime
import time
import urllib
import codecs
import optparse
import genshi.template
import lxml.etree

import blog
import reading
import tags
import homepage

def output(filename, content):
    assert isinstance(content, str)
    if os.path.exists(filename):
        existing = open(filename, 'r').read()
        if content == existing:
            print 'Skipped %s' % filename
            return
    open(filename, 'w').write(content)
    print 'Wrote %s' % filename

def main():
    # set up argument parser
    parser = optparse.OptionParser()
    parser.add_option('--config', metavar='FILENAME')
    parser.set_defaults(config='~/.constance.conf')
    options, args = parser.parse_args()

    # populate config from default location (which would have been
    # overidden by --config above, if given)
    config = SafeConfigParser()
    with codecs.open(os.path.expanduser(options.config), 'r', 'utf8') as fp:
        config.readfp(fp)

    if config.get('global', 'root'):
        os.chdir(config.get('global', 'root'))

    xslt = lxml.etree.XSLT(lxml.etree.parse(config.get('global', 'xslt')))

    if config.get('blog', 'enabled'):
        blog_entries = blog.generate('blog', xslt, config)
    else:
        blog_entries = []

    if config.get('reading', 'enabled'):
        reading_entries = reading.generate('reading_log.yaml', xslt, config)
    else:
        reading_entries = []

    if config.get('tags', 'enabled'):
        tags.generate('tags', xslt, blog_entries, config)

    for filename in os.listdir('.'):
        if filename.endswith('.html.in'):
            transformed = str(xslt(lxml.etree.parse(filename)))
            output(filename[:-3], transformed)

    if config.get('homepage', 'enabled'):
        homepage.generate('', xslt, blog_entries, 
                reading_entries, config)

if __name__ == '__main__':
    main()
