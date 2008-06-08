
# vim:encoding=utf-8

import os
from genshi.template import TemplateLoader
from colubrid import RegexApplication, HttpResponse, execute
from colubrid.exceptions import PageNotFound, HttpFound
from colubrid.server import StaticExports

import blog

ENTRIES_DIR = os.path.join(os.path.dirname(__file__), u'entries')
READINGLOG_FILE = os.path.join(os.path.dirname(__file__), u'reading_log')
BASE_URL = ''
ENTRIES_PER_PAGE = 20

template_loader = TemplateLoader(
		os.path.join(os.path.dirname(__file__), 'templates'), 
		variable_lookup='strict', 
		auto_reload=True)

class BlogApplication(RegexApplication):

	urls = [(r'^$', 'index'), 
			(r'^feed$', 'feed'), 
			(r'^\+categories/(.+)$', 'category'), 
			(r'^\+tags/(.+)$', 'tag'), 
			(r'^([^+/][^/]*)/?$', 'post')]
	charset = 'utf-8'

	def __init__(self, *args, **kwargs):
		super(BlogApplication, self).__init__(*args, **kwargs)
		self.entries = blog.Entries(ENTRIES_DIR, READINGLOG_FILE)

	def index(self):
		offset = int(self.request.args.get('offset', 0))
		sorted_entries = sorted(self.entries, key=lambda e: e.publication_date, reverse=True)[offset:offset + ENTRIES_PER_PAGE]
		format = self.request.args.get('format', 'html')
		if format == 'html':
			rendered = template_loader.load('multiple.xml').generate(
					title=None, 
					all_categories=self.entries.categories(), 
					sorted_entries=sorted_entries, 
					offset=offset,
					).render('xhtml')
			return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
		elif format == 'atom':
			rendered = template_loader.load('multiple_atom.xml').generate(
					sorted_entries=sorted_entries, 
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
					all_categories=self.entries.categories(), 
					entry=entry
					).render('xhtml')
			return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
		except blog.EntryNotFoundError:
			raise PageNotFound()

	def category(self, category):
		category = category.decode(self.charset)
		categories = self.entries.by_category()
		if category not in categories:
			raise PageNotFound()
		offset = int(self.request.args.get('offset', 0))
		entries = categories[category]
		sorted_entries = sorted(entries, key=lambda e: e.publication_date, reverse=True)[offset:offset + ENTRIES_PER_PAGE]
		rendered = template_loader.load('multiple.xml').generate(
				title=u'%s category' % category, 
				all_categories=self.entries.categories(), 
				sorted_entries=sorted_entries, 
				offset=offset
				).render('xhtml')
		return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)

	def tag(self, tag):
		tag = tag.decode(self.charset)
		by_tag = self.entries.by_tag()
		if tag not in by_tag:
			raise PageNotFound()
		offset = int(self.request.args.get('offset', 0))
		entries = by_tag[tag]
		sorted_entries = sorted(entries, key=lambda e: e.publication_date, reverse=True)[offset:offset + ENTRIES_PER_PAGE]
		rendered = template_loader.load('multiple.xml').generate(
				title=u'“%s” tag' % tag, 
				all_categories=self.entries.categories(), 
				sorted_entries=sorted_entries, 
				offset=offset
				).render('xhtml')
		return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)


app = BlogApplication
app = StaticExports(app, {'/static': os.path.join(os.path.dirname(__file__), 'static')})

if __name__ == '__main__':
	execute(app)
