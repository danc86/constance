
# vim:encoding=utf-8

import os
from itertools import chain
import wsgiref.util
from genshi.template import TemplateLoader
from colubrid import RegexApplication, HttpResponse
from colubrid.exceptions import PageNotFound, HttpFound
from colubrid.server import StaticExports

import config
import blog

template_loader = TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates'), 
        variable_lookup='strict', 
        auto_reload=True)

class Constance(RegexApplication):

    urls = [(r'^$', 'index'), 
            (r'^feed$', 'feed'), 
            (r'^\+tags/(.+)$', 'tag'), 
            (r'^\+reading/?$', 'reading'), 
            (r'^([^+/][^/]*)/?$', 'post')]
    charset = 'utf-8'

    def __init__(self, *args, **kwargs):
        super(Constance, self).__init__(*args, **kwargs)
        self.request.environ['APP_URI'] = wsgiref.util.application_uri(self.request.environ) # Colubrid ought to do this for us
        self.config = config.ConstanceConfigParser(self.request.environ['constance.config_filename'])
        self.blog_entries = blog.BlogEntrySet(self.config.getunicode('blog', 'dir'))
        readinglog_filename = self.config.getunicode('readinglog', 'filename')
        if readinglog_filename:
            self.readinglog_entries = blog.ReadingLogEntrySet(readinglog_filename)
        else:
            self.readinglog_entries = frozenset()

    def index(self):
        offset = int(self.request.args.get('offset', 0))
        sorted_entries = sorted(chain(self.blog_entries, self.readinglog_entries), 
                key=lambda e: e.publication_date, reverse=True)
        format = self.request.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=None, 
                    sorted_entries=sorted_entries, 
                    offset=offset,
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=None, 
                    self_url='%s/' % self.request.environ['APP_URI'], 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return HttpResponse(rendered, [('Content-Type', 'application/atom+xml')], 200)
        else:
            raise PageNotFound('Unknown format %r' % format)
    
    def post(self, id):
        id = id.decode(self.charset) # shouldn't Colubrid do this?
        try:
            entry = self.blog_entries[id]
            rendered = template_loader.load('single.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    entry=entry
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        except blog.EntryNotFoundError:
            raise PageNotFound()

    def tag(self, tag):
        tag = tag.decode(self.charset)
        with_tag = [e for e in self.blog_entries if tag in e.tags]
        if not with_tag:
            raise PageNotFound()
        offset = int(self.request.args.get('offset', 0))
        sorted_entries = sorted(with_tag, key=lambda e: e.publication_date, reverse=True)
        format = self.request.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=u'“%s” tag' % tag, 
                    sorted_entries=sorted_entries, 
                    offset=offset
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=u'“%s” tag' % tag, 
                    self_url='%s/+tags/%s' % (self.request.environ['APP_URI'], tag.encode(self.charset)), 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return HttpResponse(rendered, [('Content-Type', 'application/atom+xml')], 200)
        else:
            raise PageNotFound('Unknown format %r' % format)

    def reading(self):
        sorted_entries = sorted(self.readinglog_entries, key=lambda e: e.publication_date, reverse=True)
        format = self.request.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=u'reading log', 
                    sorted_entries=sorted_entries, 
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.request.environ, 
                    title=u'reading log', 
                    self_url='%s/+reading/' % self.request.environ['APP_URI'], 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return HttpResponse(rendered, [('Content-Type', 'application/atom+xml')], 200)
        else:
            raise PageNotFound('Unknown format %r' % format)

application = Constance


if __name__ == '__main__':
    import sys
    import wsgiref.simple_server
    application = StaticExports(application, {'/static': os.path.join(os.path.dirname(__file__), 'static')})
    server = wsgiref.simple_server.make_server('0.0.0.0', 8082, application)
    server.base_environ['constance.config_filename'] = sys.argv[1]
    server.serve_forever()
