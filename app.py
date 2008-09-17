
# vim:encoding=utf-8

import os, cgi, re
from itertools import chain
import wsgiref.util
from genshi.template import TemplateLoader
from colubrid.server import StaticExports
from recaptcha.client import captcha

import config
import blog

class HTTPException(Exception):
    status = '500 Internal Server Error'
    headers = []

class ForbiddenError(HTTPException):
    status = '403 Forbidden'

class NotFoundError(HTTPException):
    status = '404 Not Found'

class HTTPRedirect(HTTPException):
    def __init__(self, location):
        assert isinstance(location, str)
        self.headers = [('Location', location)]

class HTTPFound(HTTPRedirect):
    status = '302 Found'

class HTTPTemporaryRedirect(HTTPRedirect):
    status = '307 Temporary Redirect'

class HTTPPermanentRedirect(HTTPRedirect):
    status = '301 Moved Permanently'

template_loader = TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates'), 
        variable_lookup='strict', 
        auto_reload=True)

class Constance(object):

    def __init__(self, environ, start_response):
        self.environ = environ
        self.start = start_response
        # as with SCRIPT_NAME, we want APP_URI *not* to include trailing slash
        self.environ['APP_URI'] = wsgiref.util.application_uri(self.environ).rstrip('/')

        self.config = config.ConstanceConfigParser(self.environ['constance.config_filename'])

        self.encoding = self.config.get('global', 'encoding')
        self.args = dict((k.decode(self.encoding, 'ignore'), 
                          v.decode(self.encoding, 'ignore')) 
                         for k, v in 
                         cgi.parse_qsl(self.environ.get('QUERY_STRING', ''), True))
        if self.environ['REQUEST_METHOD'] == 'POST':
            maxlen = int(self.environ['CONTENT_LENGTH'])
            self.post_data = self.environ['wsgi.input'].read(maxlen)
            self.form = dict((k.decode(self.encoding, 'ignore'), 
                              v.decode(self.encoding, 'ignore')) 
                             for k, v in cgi.parse_qsl(self.post_data, True))

        self.blog_entries = blog.BlogEntrySet(self.config.getunicode('blog', 'dir'))
        readinglog_filename = self.config.getunicode('readinglog', 'filename')
        if readinglog_filename:
            self.readinglog_entries = blog.ReadingLogEntrySet(readinglog_filename)
        else:
            self.readinglog_entries = frozenset()

    def __iter__(self):
        try:
            for patt, method_name in self.urls:
                match = patt.match(self.environ['PATH_INFO'])
                if match:
                    response_body, response_headers = getattr(self, method_name)(
                            *[x.decode(self.encoding, 'ignore') for x in match.groups()])
                    status = '200 OK'
                    self.start(status, response_headers)
                    return iter([response_body])
            # no matching URI found, so give a 404
            raise NotFoundError()
        except HTTPException, e:
            # XXX make prettier errors
            self.start(e.status, [('Content-type', 'text/plain')] + e.headers)
            return iter([e.status])

    urls = [(r'/$', 'index'), 
            (r'/\+tags/$', 'tag_cloud'), 
            (r'/\+tags/(.+)$', 'tag'), 
            (r'/\+reading/?$', 'reading'), 
            (r'/([^+/][^/]*)/?$', 'post'), 
            (r'/([^+/][^/]*)/comments/\+new$', 'add_post_comment')]
    urls = [(re.compile(patt), method) for patt, method in urls]

    def index(self):
        offset = int(self.args.get('offset', 0))
        sorted_entries = sorted(chain(self.blog_entries, self.readinglog_entries), 
                key=lambda e: e.publication_date, reverse=True)
        format = self.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=None, 
                    sorted_entries=sorted_entries, 
                    offset=offset,
                    ).render('xhtml', encoding=self.encoding)
            return (rendered, [('Content-Type', 'text/html')])
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=None, 
                    self_url='%s/' % self.environ['APP_URI'], 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml', encoding=self.encoding)
            return (rendered, [('Content-Type', 'application/atom+xml')])
        else:
            raise PageNotFound('Unknown format %r' % format)
    
    def tag_cloud(self):
        tag_freqs = {}
        for entry in self.blog_entries:
            for tag in entry.tags:
                tag_freqs[tag] = tag_freqs.get(tag, 0) + 1
        rendered = template_loader.load('tag_cloud.xml').generate(
                config=self.config, 
                environ=self.environ, 
                tag_freqs=tag_freqs
                ).render('xhtml', encoding=self.encoding)
        return (rendered, [('Content-Type', 'text/html')])
    
    def post(self, id):
        try:
            entry = self.blog_entries[id]
        except KeyError:
            raise NotFoundError()
        rendered = template_loader.load('single.xml').generate(
                config=self.config, 
                environ=self.environ, 
                entry=entry
                ).render('xhtml', encoding=self.encoding)
        return (rendered, [('Content-Type', 'text/html')])
    
    def add_post_comment(self, id):
        entry = self.blog_entries[id]

        if self.config.getboolean('blog', 'require_captcha'):
            # first verify the captcha
            captcha_response = captcha.submit(
                    self.form['recaptcha_challenge_field'], 
                    self.form['recaptcha_response_field'], 
                    self.config.get('blog', 'recaptcha_privkey'), 
                    self.environ['REMOTE_ADDR'])
            if not captcha_response.is_valid:
                raise ValueError(captcha_response.error_code) # XXX handle better

        try:
            metadata = {}
            metadata['From'] = self.form['from'] or u'Anonymous'
            if self.form['author-url']:
                metadata['Author-URL'] = self.form['author-url']
            if self.form['author-email']:
                metadata['Author-Email'] = self.form['author-email']
            if self.environ['HTTP_USER_AGENT']:
                metadata['User-Agent'] = self.environ['HTTP_USER_AGENT']
            if self.environ['REMOTE_ADDR']:
                metadata['Received'] = u'from %s' % self.environ['REMOTE_ADDR']
            entry.add_comment(metadata, self.form['comment'])
            raise HTTPFound('%s/%s/' % (self.environ.get('APP_URI', ''), 
                    id.encode(self.encoding)))
        except blog.CommentingForbiddenError:
            raise ForbiddenError()

    def tag(self, tag):
        with_tag = [e for e in self.blog_entries if tag in e.tags]
        if not with_tag:
            raise NotFoundError()
        offset = int(self.args.get('offset', 0))
        sorted_entries = sorted(with_tag, key=lambda e: e.publication_date, reverse=True)
        format = self.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=u'“%s” tag' % tag, 
                    sorted_entries=sorted_entries, 
                    offset=offset
                    ).render('xhtml')
            return (rendered, [('Content-Type', 'text/html')])
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=u'“%s” tag' % tag, 
                    self_url='%s/+tags/%s' % (self.environ['APP_URI'], tag.encode(self.encoding)), 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml')
            return (rendered, [('Content-Type', 'application/atom+xml')])
        else:
            raise PageNotFound('Unknown format %r' % format)

    def reading(self):
        sorted_entries = sorted(self.readinglog_entries, key=lambda e: e.publication_date, reverse=True)
        format = self.args.get('format', 'html')
        if format == 'html':
            rendered = template_loader.load('multiple.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=u'reading log', 
                    sorted_entries=sorted_entries, 
                    ).render('xhtml', encoding=self.encoding)
            return (rendered, [('Content-Type', 'text/html')])
        elif format == 'atom':
            rendered = template_loader.load('multiple_atom.xml').generate(
                    config=self.config, 
                    environ=self.environ, 
                    title=u'reading log', 
                    self_url='%s/+reading/' % self.environ['APP_URI'], 
                    sorted_entries=sorted_entries[:self.config.getint('global', 'entries_in_feed')], 
                    feed_updated=sorted_entries[0].modified_date
                    ).render('xml', encoding=self.encoding)
            return (rendered, [('Content-Type', 'application/atom+xml')])
        else:
            raise NotFoundError('Unknown format %r' % format)

application = Constance


if __name__ == '__main__':
    import sys
    import wsgiref.simple_server
    application = StaticExports(application, {'/static': os.path.join(os.path.dirname(__file__), 'static')})
    server = wsgiref.simple_server.make_server('0.0.0.0', 8082, application)
    server.base_environ['constance.config_filename'] = sys.argv[1]
    server.serve_forever()
