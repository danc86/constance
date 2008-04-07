import os
from genshi.template import TemplateLoader

from blog import BASE_DIR, Entry

template_loader = TemplateLoader(os.path.join(BASE_DIR, 'templates'), auto_reload=True)

def post(id):
	print template_loader.load('post.xml').generate(entry=Entry(id)).render('xhtml')
