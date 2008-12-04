
# vim:encoding=utf-8

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

import cgi, re, datetime, urllib
from itertools import chain
import genshi.template
from webob import Request, Response
from webob import exc
from recaptcha.client import captcha

import config
from itemtypes import *

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates'), 
        variable_lookup='strict', 
        auto_reload=True)

class Constance(object):

    def __init__(self, environ, start_response):
        self.environ = environ
        self.start = start_response

        self.config = config.ConstanceConfigParser(self.environ['constance.config_filename'])
        self.encoding = self.config.get('global', 'encoding')

        self.req = Request(environ)
        self.req.charset = self.encoding

        self.item_sets = eval(self.config.get('global', 'item_sets'))

    def __iter__(self):
        try:
            resp = self.dispatch()
        except exc.HTTPException, e:
            resp = e
        return iter(resp(self.environ, self.start))

    urls = [(r'/(?:index)?$', 'index'), 
            (r'/tags/$', 'tag_cloud'), 
            (r'/tags/(.+)$', 'tag'), 
            (r'/sitemap.xml$', 'sitemap')]
    urls = [(re.compile(patt), method) for patt, method in urls]
    def dispatch(self):
        if self.req.path_info.endswith('.atom'):
            self.req.format = 'application/atom+xml'
            self.req.path_info = self.req.path_info[:-5]
        else:
            self.req.format = self.req.accept.best_match(['text/html', 'application/atom+xml']) # XXX don't hardcode

        path_info = urllib.unquote(self.req.path_info).decode(self.encoding)

        # first, try the predefined urls above
        for patt, method in self.urls:
            m = patt.match(path_info)
            if m is not None:
                return getattr(self, method)(*m.groups())

        # next, try the item sets
        for item_set in self.item_sets:
            try:
                result = item_set.get(path_info)
            except NotExistError, e:
                pass
            else:
                if hasattr(result, '__iter__'):
                    return self.render_multiple(result)
                else:
                    return self.render_single(result)

        # no matching URI found, so give a 404
        raise exc.HTTPNotFound().exception

    def render_single(self, item):
        if self.req.format == 'text/html':
            template = template_loader.load('html/single.xml')
            rendered = template.generate(
                    config=self.config, 
                    item=item
                    ).render('xhtml')
        else:
            raise exc.HTTPBadRequest('Unacceptable format for render_single %r' % self.req.format).exception
        return Response(rendered, content_type=self.req.format)

    def render_multiple(self, items):
        try:
            offset = int(self.req.GET.get('offset', 0))
        except ValueError:
            raise exc.HTTPBadRequest('Invalid offset %r' % self.GET['offset']).exception
        if self.req.format == 'text/html':
            template = template_loader.load('html/multiple.xml')
            rendered = template.generate(
                    config=self.config, 
                    items=items, 
                    title=None, 
                    offset=offset
                    ).render('xhtml')
        elif self.req.format == 'application/atom+xml':
            template = template_loader.load('atom/multiple.xml')
            rendered = template.generate(
                    config=self.config, 
                    items=items, 
                    title=None, 
                    self_url=self.req.path_url
                    ).render('xml')
        else:
            raise exc.HTTPBadRequest('Unacceptable format for render_multiple %r' % self.req.format).exception
        return Response(rendered, content_type=self.req.format)

    def index(self):
        items = chain(*self.item_sets)
        return self.render_multiple(items)
    
    def tag_cloud(self):
        tag_freqs = {}
        for entry in chain(*self.item_sets):
            for tag in entry.tags:
                tag_freqs[tag] = tag_freqs.get(tag, 0) + 1
        if self.req.format == 'text/html':
            rendered = template_loader.load('html/tag_cloud.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    tag_freqs=tag_freqs
                    ).render('xhtml', encoding=self.encoding)
        else:
            raise exc.HTTPBadRequest('Unacceptable format for render_multiple %r' % self.req.format).exception
        return Response(rendered, content_type=self.req.format)
    
    def add_post_comment(self, id):
        entry = self.blog_entries[id]

        if self.config.getboolean('blog', 'require_captcha'):
            # first verify the captcha
            if ('recaptcha_challenge_field' not in self.req.POST or 
                    'recaptcha_response_field' not in self.req.POST):
                raise exc.HTTPForbidden('CAPTCHA form values missing. Are you a bot?').exception
            captcha_response = captcha.submit(
                    self.req.POST['recaptcha_challenge_field'], 
                    self.req.POST['recaptcha_response_field'], 
                    self.config.get('blog', 'recaptcha_privkey'), 
                    self.req.remote_addr)
            if not captcha_response.is_valid:
                raise exc.HTTPForbidden('You failed the CAPTCHA. Please try submitting again. '
                        '(reCAPTCHA error code: %s)' % captcha_response.error_code).exception

        try:
            metadata = {}
            metadata['From'] = self.req.POST['from'] or u'Anonymous'
            if self.req.POST['author-url']:
                metadata['Author-URL'] = self.req.POST['author-url']
            if self.req.POST['author-email']:
                metadata['Author-Email'] = self.req.POST['author-email']
            if self.req.headers['User-Agent']:
                metadata['User-Agent'] = self.req.headers['User-Agent']
            if self.req.remote_addr:
                metadata['Received'] = u'from %s' % self.req.remote_addr
            entry.add_comment(metadata, self.req.POST['comment'])
            raise exc.HTTPFound('%s/%s/' % (self.req.application_url, 
                    id.encode(self.encoding))).exception
        except blog.CommentingForbiddenError:
            raise exc.HTTPForbidden('Commenting is disabled for this entry.').exception

    def tag(self, tag):
        with_tag = [e for e in chain(*self.item_sets) if tag in e.tags]
        if not with_tag:
            raise exc.HTTPNotFound().exception
        return self.render_multiple(with_tag)

    def sitemap(self):
        tags = {}
        for entry in self.blog_entries:
            for tag in entry.tags:
                tags[tag] = max(entry.modified_date, tags.get(tag, datetime.datetime.min))
        sorted_blog_entries = sorted(self.blog_entries, 
                key=lambda e: e.publication_date, reverse=True)
        sorted_entries = sorted(chain(self.blog_entries, self.readinglog_entries), 
                key=lambda e: e.publication_date, reverse=True)
        readinglog_entries = list(self.readinglog_entries)
        if len(readinglog_entries) != 0:
            rl_updated = max(e.date for e in readinglog_entries)
        else:
            rl_updated = None
        rendered = template_loader.load('sitemap.xml').generate(
                config=self.config, 
                environ=self.environ, 
                blog_entries=self.blog_entries, 
                tags=tags, 
                readinglog_updated=rl_updated,
                blog_index_updated=max(e.modified_date for e in sorted_blog_entries[:self.config.getint('global', 'entries_per_page')]), 
                index_updated=max(e.modified_date for e in sorted_entries[:self.config.getint('global', 'entries_per_page')]), 
                ).render('xml', encoding='utf8') # sitemaps must be UTF-8
        return Response(rendered, content_type='text/xml')

application = Constance

if __name__ == '__main__':
    import optparse
    parser = optparse.OptionParser(usage='%prog [OPTIONS...] CONFIG_FILENAME')
    parser.set_defaults(port=8082)
    parser.add_option('-p', '--port', type='int', 
            help='Port to server on (default: %default)')
    options, args = parser.parse_args()
    if not args:
        parser.error('You must supply a CONFIG_FILENAME')

    from paste.urlparser import StaticURLParser
    from paste.urlmap import URLMap
    application = URLMap()
    application['/static'] = StaticURLParser(os.path.join(os.path.dirname(__file__), 'static'))
    application['/'] = Constance

    import wsgiref.simple_server
    server = wsgiref.simple_server.make_server('0.0.0.0', options.port, application)
    server.base_environ['constance.config_filename'] = args[0]
    server.serve_forever()
