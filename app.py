
# vim:encoding=utf-8

import os
import wsgiref.util
from genshi.template import TemplateLoader
from colubrid import RegexApplication, HttpResponse, execute
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
            (r'^([^+/][^/]*)/?$', 'post')]
    charset = 'utf-8'

    def __init__(self, *args, **kwargs):
        super(Constance, self).__init__(*args, **kwargs)
        self.request.environ['APP_URI'] = wsgiref.util.application_uri(self.request.environ) # Colubrid ought to do this for us
        self.entries = blog.Entries(config.ENTRIES_DIR, config.READINGLOG_FILE)

    def index(self):
        offset = int(self.request.args.get('offset', 0))
        sorted_entries = sorted(self.entries, key=lambda e: e.publication_date, reverse=True)
        format = self.request.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    environ=self.request.environ, 
                    title=None, 
                    sorted_entries=sorted_entries, 
                    offset=offset,
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    environ=self.request.environ, 
                    title=None, 
                    self_url='%s/' % self.request.environ['APP_URI'], 
                    sorted_entries=sorted_entries[:config.ENTRIES_PER_PAGE], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return HttpResponse(rendered, [('Content-Type', 'application/atom+xml')], 200)
        else:
            raise PageNotFound('Unknown format %r' % format)
    
    def post(self, id):
        id = id.decode(self.charset) # shouldn't Colubrid do this?
        try:
            entry = self.entries[id]
            rendered = template_loader.load('single.xml').generate(
                    environ=self.request.environ, 
                    entry=entry
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        except blog.EntryNotFoundError:
            raise PageNotFound()

    def tag(self, tag):
        tag = tag.decode(self.charset)
        by_tag = self.entries.by_tag()
        if tag not in by_tag:
            raise PageNotFound()
        offset = int(self.request.args.get('offset', 0))
        entries = by_tag[tag]
        sorted_entries = sorted(entries, key=lambda e: e.publication_date, reverse=True)
        format = self.request.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    environ=self.request.environ, 
                    title=u'“%s” tag' % tag, 
                    sorted_entries=sorted_entries, 
                    offset=offset
                    ).render('xhtml')
            return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    environ=self.request.environ, 
                    title=u'“%s” tag' % tag, 
                    self_url='%s/+tags/%s' % (self.request.environ['APP_URI'], tag.encode(self.charset)), 
                    sorted_entries=sorted_entries[:config.ENTRIES_PER_PAGE], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return HttpResponse(rendered, [('Content-Type', 'application/atom+xml')], 200)
        else:
            raise PageNotFound('Unknown format %r' % format)


if __name__ == '__main__':
    app = Constance
    app = StaticExports(app, {'/static': os.path.join(os.path.dirname(__file__), 'static')})
    execute(app, hostname='0.0.0.0', port=8082)
