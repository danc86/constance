
# vim:encoding=utf-8

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

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

def main():
    parser = optparse.OptionParser()
    parser.add_option('--blog-dir', metavar='DIR')
    parser.add_option('--reading-log', metavar='FILENAME')
    parser.add_option('--tags-dir', metavar='DIR')
    parser.add_option('--root-dir', metavar='DIR')
    parser.add_option('--xslt', metavar='FILENAME')
    parser.set_defaults(blog_dir='./blog/',
            reading_log=None,
            tags_dir='./tags/',
            root_dir='./',
            xslt='./style.xsl')
    options, args = parser.parse_args()

    xslt = lxml.etree.XSLT(lxml.etree.parse(options.xslt))
    blog_entries = blog.generate(options.blog_dir, xslt)
    if options.reading_log is not None:
        reading_entries = reading.generate(options.reading_log, xslt)
    else:
        reading_entries = []
    tags.generate(options.tags_dir, xslt, blog_entries)
    for filename in os.listdir(options.root_dir):
        if filename.endswith('.html.in'):
            transformed = str(xslt(lxml.etree.parse(filename)))
            output(filename[:-3], transformed)
    homepage.generate(options.root_dir, xslt, blog_entries, reading_entries)

if __name__ == '__main__':
    main()
