
# vim:encoding=utf-8

import os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'lib'))

import cgi, re, datetime
from itertools import chain
import wsgiref.util
from genshi.template import TemplateLoader
from colubrid.server import StaticExports
from recaptcha.client import captcha

import config
import blog

class HTTPException(Exception):
    status = '500 Internal Server Error'
    message = 'An internal error occurred.'
    headers = []
    def __init__(self, message=None):
        if message is not None: self.message = message

class ForbiddenError(HTTPException):
    status = '403 Forbidden'
    message = 'You do not have access to the requested resource.'

class NotFoundError(HTTPException):
    status = '404 Not Found'
    message = 'The requested resource could not be found.'

class HTTPRedirect(HTTPException):
    def __init__(self, location):
        assert isinstance(location, str)
        self.headers = [('Location', location)]

class HTTPFound(HTTPRedirect):
    status = '302 Found'
    message = 'The requested resource is located at a different URL.'

class HTTPTemporaryRedirect(HTTPRedirect):
    status = '307 Temporary Redirect'
    message = 'The requested resource is temporarily located at a different URL.'

class HTTPPermanentRedirect(HTTPRedirect):
    status = '301 Moved Permanently'
    message = 'The requested resource has moved permanently to a different URL.'

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

        self.blog_entries = blog.BlogEntrySet(self.config.get('blog', 'dir'))
        readinglog_filename = self.config.get('readinglog', 'filename')
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
            return self.error_response(e)

    def error_response(self, error):
        # XXX should probably just use real templates here ...
        body = u"""<html><head><title>%s - %s</title>
                <link rel="stylesheet" type="text/css" href="%s/static/css/common.css" />
                </head><body><div id="contentwrapper"><div id="content">
                <h2>%s</h2><p>%s</p></div></div></body></html>""" % (
                error.status, self.config.getunicode('global', 'name'), 
                self.environ['SCRIPT_NAME'], error.status, error.message)
        self.start(error.status, [('Content-type', 'text/html')] + error.headers)
        return iter([body.encode(self.encoding)])

    # XXX keep sitemap in sync with these
    urls = [(r'/$', 'index'), 
            (r'/\+tags/$', 'tag_cloud'), 
            (r'/\+tags/(.+)$', 'tag'), 
            (r'/\+reading/?$', 'reading'), 
            (r'/sitemap.xml$', 'sitemap'), 
            (r'/([^+/][^/]*)/?$', 'post'), 
            (r'/([^+/][^/]*)/comments/\+new$', 'add_post_comment')]
    urls = [(re.compile(patt), method) for patt, method in urls]

    def index(self):
        try:
            offset = int(self.args.get('offset', 0))
        except ValueError:
            raise NotFoundError('Invalid offset %r' % self.args['offset'])
        sorted_entries = sorted(chain(self.blog_entries, self.readinglog_entries), 
                key=lambda e: e.publication_date, reverse=True)
        if offset >= len(sorted_entries):
            raise NotFoundError('Offset beyond end of entries')
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
                    feed_updated=max(e.modified_date for e in sorted_entries[:self.config.getint('global', 'entries_in_feed')])
                    ).render('xml', encoding=self.encoding)
            return (rendered, [('Content-Type', 'application/atom+xml')])
        else:
            raise NotFoundError('Unknown format %r' % format)
    
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
            if ('recaptcha_challenge_field' not in self.form or 
                    'recaptcha_response_field' not in self.form):
                raise ForbiddenError('CAPTCHA form values missing. Are you a bot?')
            captcha_response = captcha.submit(
                    self.form['recaptcha_challenge_field'], 
                    self.form['recaptcha_response_field'], 
                    self.config.get('blog', 'recaptcha_privkey'), 
                    self.environ['REMOTE_ADDR'])
            if not captcha_response.is_valid:
                raise ForbiddenError('You failed the CAPTCHA. Please try submitting again. '
                        '(reCAPTCHA error code: %s)' % captcha_response.error_code)

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
            raise ForbiddenError('Commenting is disabled for this entry.')

    def tag(self, tag):
        with_tag = [e for e in self.blog_entries if tag in e.tags]
        if not with_tag:
            raise NotFoundError()
        try:
            offset = int(self.args.get('offset', 0))
        except ValueError:
            raise NotFoundError('Invalid offset %r' % self.args['offset'])
        sorted_entries = sorted(with_tag, key=lambda e: e.publication_date, reverse=True)
        if offset >= len(sorted_entries):
            raise NotFoundError('Offset beyond end of entries')
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
            raise NotFoundError('Unknown format %r' % format)

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

    def sitemap(self):
        tags = {}
        for entry in self.blog_entries:
            for tag in entry.tags:
                tags[tag] = max(entry.modified_date, tags.get(tag, datetime.datetime.min))
        sorted_entries = sorted(chain(self.blog_entries, self.readinglog_entries), 
                key=lambda e: e.publication_date, reverse=True)
        if len(self.readinglog_entries) != 0:
            rl_updated = max(e.date for e in self.readlinglog_entries)
        else:
            rl_updated = None
        rendered = template_loader.load('sitemap.xml').generate(
                config=self.config, 
                environ=self.environ, 
                blog_entries=self.blog_entries, 
                tags=tags, 
                readinglog_updated=rl_updated,
                index_updated=max(e.modified_date for e in sorted_entries[:self.config.getint('global', 'entries_per_page')]), 
                ).render('xml', encoding='utf8') # sitemaps must be UTF-8
        return (rendered, [('Content-Type', 'text/xml')])

application = Constance


if __name__ == '__main__':
    import wsgiref.simple_server
    application = StaticExports(application, {'/static': os.path.join(os.path.dirname(__file__), 'static')})
    server = wsgiref.simple_server.make_server('0.0.0.0', 8082, application)
    server.base_environ['constance.config_filename'] = sys.argv[1]
    server.serve_forever()
