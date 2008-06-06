import os
from genshi.template import TemplateLoader
from colubrid import RegexApplication, HttpResponse, execute
from colubrid.exceptions import PageNotFound, HttpFound
from colubrid.server import StaticExports

from blog import Entries

ENTRIES_DIR = os.path.join(os.path.dirname(__file__), u'entries')
BASE_URL = ''

template_loader = TemplateLoader(
		os.path.join(os.path.dirname(__file__), 'templates'), 
		variable_lookup='strict', 
		auto_reload=True)

class BlogApplication(RegexApplication):

	urls = [(r'^$', 'index'), 
			(r'^feed$', 'feed'), 
			(r'^([^/]+)/?$', 'post')]
	charset = 'utf-8'

	def __init__(self, *args, **kwargs):
		super(BlogApplication, self).__init__(*args, **kwargs)
		self.entries = Entries(ENTRIES_DIR)

	def index(self):
		rendered = template_loader.load('index.xml').generate(entries=self.entries).render('xhtml')
		return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)
	
	def post(self, id):
		id = id.decode(self.charset) # shouldn't Colubrid do this?
		entry = self.entries[id]
		rendered = template_loader.load('single.xml').generate(entry=entry).render('xhtml')
		return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)

app = BlogApplication
app = StaticExports(app, {'/static': os.path.join(os.path.dirname(__file__), 'static')})

if __name__ == '__main__':
	execute(app)
