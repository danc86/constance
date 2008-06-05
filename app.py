import os
from genshi.template import TemplateLoader
from colubrid import RegexApplication, HttpResponse, execute
from colubrid.exceptions import PageNotFound, HttpFound
from colubrid.server import StaticExports

from blog import Entry

template_loader = TemplateLoader(
		os.path.join(os.path.dirname(__file__), 'templates'), 
		auto_reload=True)

class BlogApplication(RegexApplication):

	urls = [(r'^$', 'index'), 
			(r'^feed$', 'feed'), 
			(r'^([^/]+)/?$', 'post')]
	charset = 'utf-8'

	def index(self):
		return HttpResponse('blah')
	
	def post(self, id):
		rendered = template_loader.load('post.xml').generate(entry=Entry(id)).render('xhtml')
		return HttpResponse(rendered, [('Content-Type', 'text/html')], 200)

app = BlogApplication
app = StaticExports(app, {'/static': os.path.join(os.path.dirname(__file__), 'static')})

if __name__ == '__main__':
	execute(app)
