import os
from datetime import datetime
import markdown


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


class Entries(object):

	def __init__(self, entries_dir):
		self.entries_dir = entries_dir
	
	def __contains__(self, id):
		return os.path.exists(os.path.join(self.entries_dir, id))
	
	def __getitem__(self, id):
		return Entry(self.entries_dir, id)
	
	def __iter__(self):
		return (Entry(self.entries_dir, filename) 
				for filename in os.listdir(self.entries_dir)
				if not filename.startswith('.'))


class Entry(object):

	def __init__(self, entries_dir, id):
		assert isinstance(id, unicode), id
		self.id = id
		self.dir = os.path.join(entries_dir, id)
		self.comments_dir = os.path.join(self.dir, 'comments')

		if not os.path.exists(self.dir):
			raise EntryNotFoundError()
		if not os.access(self.dir, os.R_OK):
			raise EntryForbiddenError()

		self.raw = open(os.path.join(self.dir, 'content.txt'), 'r').read().decode('utf-8')
		md = markdown.Markdown(extensions=['meta'])
		self.body = md.convert(self.raw)
		self.metadata = cleanup_metadata(md.Meta)
		self.title = self.metadata['title']

		raw_cats = self.metadata.get('categories', '').strip()
		if raw_cats:
			self.categories = [cat.strip() for cat in raw_cats.split(',')]
		else:
			self.categories = []
		raw_tags = self.metadata.get('tags', '').strip()
		if raw_tags:
			self.tags = [tag.strip() for tag in raw_tags.split(',')]
		else:
			self.tags = []

		self.modified_date = datetime.fromtimestamp(os.path.getmtime(os.path.join(self.dir, 'content.txt')))
		self.publication_date = self.metadata.get('publication-date', None) or self.modified_date

	def comments(self):
		return Comments(self.comments_dir)

	def has_comments(self):
		"""
		Returns True if this Entry could *possibly* have comments, although it 
		may still have no comments (yet).
		"""
		return os.path.isdir(self.comments_dir) and \
				os.access(self.comments_dir, os.R_OK)


class Comments(object):

	def __init__(self, path):
		self.path = path
	
	def __contains__(self, id):
		return os.path.exists(os.path.join(self.path, id))
	
	def __getitem__(self, id):
		return Comment(self.path, id)
	
	def __iter__(self):
		return (Comment(self.path, filename) 
				for filename in os.listdir(self.path)
				if not filename.startswith('.'))


class Comment(object):

	def __init__(self, comments_dir, id):
		path = os.path.join(comments_dir, id)
		if not os.path.exists(path):
			raise CommentNotFoundError()
		if not os.access(path, os.R_OK):
			raise CommentForbiddenError()

		self.id = id
		self.raw = open(path, 'r').read().decode('utf-8')
		md = markdown.Markdown(extensions=['meta'])
		self.body = md.convert(self.raw)
		if not hasattr(md, 'Meta'): raise Exception(self.raw)
		self.metadata = md.Meta
		
		self.author = self.metadata.get('from', None)
		self.author_url = self.metadata.get('author-url', None)
		self.date = datetime.fromtimestamp(os.path.getmtime(path))

	def author_name(self):
		return self.author or u'Anonymous'
