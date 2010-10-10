
# vim:encoding=utf-8

import os
import genshi.template
import lxml.etree

import constance
import viewutils

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates', 'tags'), 
        variable_lookup='strict')

def generate(dir, xslt, blog_entries, template_config):
    tag_freqs = {}
    for entry in blog_entries:
        for tag in entry.tags:
            tag_freqs[tag] = tag_freqs.get(tag, 0) + 1

    for tag in tag_freqs.keys():
        tagged_entries = [e for e in blog_entries if tag in e.tags]
        rendered = template_loader.load('tag.html').generate(tag=tag, items=tagged_entries).render('xhtml')
        transformed = str(xslt(lxml.etree.fromstring(rendered)))
        constance.output(os.path.join(dir, tag.encode('utf8') + '.html'), transformed)

    rendered = template_loader.load('index.html').generate(tag_freqs=tag_freqs,
            template_config=template_config).render('xhtml')
    transformed = str(xslt(lxml.etree.fromstring(rendered)))
    constance.output(os.path.join(dir, 'index.html'), transformed)
