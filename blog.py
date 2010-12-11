
# vim:encoding=utf-8

import os
import re
import email
from datetime import datetime
import genshi.template
import lxml.etree

import constance
import viewutils

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.realpath(os.path.dirname(__file__)), 'templates', 'blog'), 
        variable_lookup='strict')

def cleanup_metadata(header_items):
    cleaned = {}
    for k, v in header_items:
        k = k.lower()
        if k.endswith('date'):
            v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
        else:
            v = v.decode('utf8') # XXX encoding
        cleaned[k] = v
    return cleaned

class BlogEntry(object):

    def __init__(self, dir, name):
        content_filename = os.path.join(dir, name + '.txt')
        self.id = name.decode('utf8')

        # not really a MIME document, but parse it like one
        msg = email.message_from_file(open(content_filename, 'r'))
        self.metadata = cleanup_metadata(msg.items())
        self.body = viewutils.markdown(msg.get_payload().decode('utf8'))
        self.title = viewutils.mini_markdown(self.metadata['title'])

        raw_tags = self.metadata.get('tags', '').strip()
        if raw_tags:
            self.tags = frozenset(tag.strip() for tag in raw_tags.split(','))
        else:
            self.tags = frozenset()

        self.modified_date = datetime.fromtimestamp(os.path.getmtime(content_filename))
        self.publication_date = self.metadata.get('publication-date', None) or self.modified_date
        self.guid = self.metadata['guid']
        self.language = self.metadata.get('language', None)

    def generate_atom(self, config):
        return template_loader.load('entry.atom').generate(item=self,
                config=config)

class BlogEntrySet(object):

    def __init__(self, dir):
        self.dir = dir
        self.entries = []
        for filename in os.listdir(dir):
            m = re.match(r'([^.].*)\.txt$', filename)
            if m:
                self.entries.append(BlogEntry(dir, m.group(1)))
    
    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

def generate(dir, xslt, config):
    entries = BlogEntrySet(dir)
    
    for entry in entries:
        rendered = template_loader.load('entry.html').generate(item=entry,
                config=config).render('xhtml')
        transformed = str(xslt(lxml.etree.fromstring(rendered)))
        constance.output(os.path.join(dir, entry.id.encode('utf8') + '.html'), transformed)
    
    # index
    rendered = template_loader.load('index.html').generate(items=entries,
            config=config).render('xhtml')
    transformed = str(xslt(lxml.etree.fromstring(rendered)))
    constance.output(os.path.join(dir, 'index.html'), transformed)

    # feed
    rendered = template_loader.load('index.atom').generate(items=entries,
            config=config).render('xml')
    constance.output(os.path.join(dir, 'index.atom'), rendered)

    return entries
