
# vim:encoding=utf-8

import os
import genshi.template
import yaml
import lxml.etree

import constance
import viewutils

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates', 'reading'), 
        variable_lookup='strict')

class ReadingLogEntry(object):

    def __init__(self, yaml_dict):
        self.title = viewutils.mini_markdown(yaml_dict['Title'])
        self.author = yaml_dict['Author']
        self.publication_date = self.modified_date = self.date = yaml_dict['Date']
        self.url = yaml_dict.get('URL', None)
        self.isbn = yaml_dict.get('ISBN', None)
        self.rating = yaml_dict.get('Rating', None)
        self.tags = frozenset()
        self.guid = yaml_dict['GUID']

    def generate_atom(self, template_config):
        return template_loader.load('entry.atom').generate(item=self,
                template_config=template_config)

class ReadingLogEntrySet(object):

    def __init__(self, filename):
        self.filename = filename
        self.entries = []
        for d in yaml.load_all(open(self.filename, 'r')):
            self.entries.append(ReadingLogEntry(d))

    def __iter__(self):
        return iter(self.entries)

    def __len__(self):
        return len(self.entries)

def generate(filename, xslt, template_config):
    entries = ReadingLogEntrySet(filename)

    rendered = template_loader.load('reading.html').generate(items=entries,
            template_config=template_config).render('xhtml')
    transformed = str(xslt(lxml.etree.fromstring(rendered)))
    constance.output(os.path.join(os.path.dirname(filename), 'reading.html'), transformed)

    # feed
    rendered = template_loader.load('reading.atom').generate(items=entries,
            template_config=template_config).render('xml')
    constance.output(os.path.join(os.path.dirname(filename), 'reading.atom'), rendered)

    return entries
