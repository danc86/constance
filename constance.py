
# vim:encoding=utf-8

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

from ConfigParser import SafeConfigParser
import re
import datetime
import time
import urllib
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

default_config = """[paths]
blog = ./blog/
reading_log =
tags = ./tags/
root = ./
xslt = ./style.xsl

[template]
website = http://localhost
"""

def main():
    config_filename = os.path.expanduser('~/.constance')

    # set up argument parser
    parser = optparse.OptionParser()
    parser.add_option('--config', metavar='FILENAME')
    parser.set_defaults(config=config_filename)
    options, args = parser.parse_args()

    # populate config from default location (which would have been
    # overidden by --config above, if given)
    config = SafeConfigParser(allow_no_value=True)
    with open(options.config, 'r') as fp:
        config.readfp(fp)
    template_config = dict(config.items('template'))

    # strip trailing slash if it was given
    website = config.get('template', 'website')
    if website[-1] == '/':
        website = website[:-1]

    xslt = lxml.etree.XSLT(lxml.etree.parse(config.get('paths', 'xslt')))

    blog_entries = blog.generate(config.get('paths', 'blog'), xslt,
            template_config=template_config)

    rl_path = config.get('paths', 'reading_log')
    if rl_path is not None and rl_path != '': # XXX allow_no_value is broken?
        reading_entries = reading.generate(rl_path, xslt, 
                template_config=template_config)
    else:
        reading_entries = []

    tags.generate(config.get('paths', 'tags'), xslt, blog_entries, 
            template_config=template_config)

    for filename in os.listdir(config.get('paths', 'root')):
        if filename.endswith('.html.in'):
            transformed = str(xslt(lxml.etree.parse(filename)))
            output(filename[:-3], transformed)

    homepage.generate(config.get('paths', 'root'), xslt, blog_entries, 
            reading_entries, template_config=template_config)

if __name__ == '__main__':
    main()
