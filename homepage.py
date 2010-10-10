
# vim:encoding=utf-8

import os
from itertools import chain
import genshi.template
import lxml.etree

import constance
import viewutils

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates', 'homepage'), 
        variable_lookup='strict')

def generate(dir, xslt, blog_entries, reading_entries, website):
    # index
    template = template_loader.load('index.html')
    rendered = template.generate(blog_entries=blog_entries, 
            reading_entries=reading_entries, website=website).render('xhtml')
    transformed = str(xslt(lxml.etree.fromstring(rendered)))
    constance.output(os.path.join(dir, 'index.html'), transformed)

    # firehose
    rendered = template_loader.load('firehose.atom').generate(
            items=chain(blog_entries, reading_entries),
            website=website).render('xml')
    constance.output(os.path.join(dir, 'firehose.atom'), rendered)
