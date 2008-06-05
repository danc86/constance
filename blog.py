import os
from datetime import datetime
import markdown


BASE_DIR = '.'
BASE_URL = ''


def cleanup_metadata(meta):
	cleaned = {}
	for k, v in meta.iteritems():
		v = '\n'.join(v)
		if k.endswith('date'):
			v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
		cleaned[k] = v
	return cleaned


class EntryNotFoundError(ValueError): pass

class EntryForbiddenError(ValueError): pass

class CommentNotFoundError(ValueError): pass

class CommentForbiddenError(ValueError): pass


class Entry(object):

	def __init__(self, id):
		self.id = id
		self.dir = os.path.join(BASE_DIR, id)
		self.comments_dir = os.path.join(self.dir, 'comments')

		if not os.path.exists(self.dir):
			raise EntryNotFoundError()
		if not os.access(self.dir, os.R_OK):
			raise EntryForbiddenError()

		self.raw = open(os.path.join(self.dir, 'content.txt'), 'r').read()
		md = markdown.Markdown(extensions=['meta'])
		self.body = md.convert(self.raw)
		self.metadata = cleanup_metadata(md.Meta)
		self.title = self.metadata['title']

		self.categories = [cat.strip() for cat in self.metadata.get('categories', '').split(',')]
		self.tags = [tag.strip() for tag in self.metadata.get('tags', '').split(',')]

		self.modified_date = datetime.fromtimestamp(os.path.getmtime(os.path.join(self.dir, 'content.txt')))
		self.publication_date = self.metadata.get('publication-date', None) or self.modified_date

	def permalink(self):
		return '%s/%s/' % (BASE_URL, self.id)

	def has_comments(self):
		"""
		Returns True if this Entry could *possibly* have comments, although it 
		may still have no comments (yet).
		"""
		return os.path.isdir(self.comments_dir) and \
				os.access(self.comments_dir, os.R_OK)

	def comments(self):
		for filename in sorted(os.listdir(self.comments_dir), key=int):
			yield Comment(os.path.join(self.comments_dir, filename))

	def comment(self, id):
		return Comment(os.path.join(self.comments_dir, str(id)))


class Comment(object):

	def __init__(self, path):
		if not os.path.exists(path):
			raise CommentNotFoundError()
		if not os.access(path, os.R_OK):
			raise CommentForbiddenError()

		self.raw = open(path, 'r').read()
		md = markdown.Markdown(extensions=['meta'])
		self.body = md.convert(self.raw)
		self.metadata = md.Meta
		
		self.author = self.metadata.get('from', None)
		self.date = self.metadata['date']

	def author_link(self):
		return self.author or u'Anonymous'
