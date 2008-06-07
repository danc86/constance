import os, re
from datetime import datetime
from itertools import chain
import markdown
import genshi
import yaml


def count(iterable):
	count = 0
	for _ in iterable:
		count += 1
	return count

def cleanup_metadata(meta):
	cleaned = {}
	for k, v in meta.iteritems():
		v = '\n'.join(v)
		if k.endswith('date'):
			v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
		cleaned[k] = v
	return cleaned

def mini_markdown(s):
	# XXX find a more efficient way to do this?
	m = markdown.Markdown(extensions=['typography']).convert(s)
	the_p, = re.match(u'<p>(.*)\n</p>', m).groups()	
	return genshi.Markup(the_p)


class EntryNotFoundError(ValueError): pass

class EntryForbiddenError(ValueError): pass

class CommentNotFoundError(ValueError): pass

class CommentForbiddenError(ValueError): pass


class Entries(object):

	def __init__(self, entries_dir, readinglog_file):
		self.entries_dir = entries_dir
		self.readinglog_file = readinglog_file
	
	def __contains__(self, id):
		return os.path.exists(os.path.join(self.entries_dir, id))
	
	def __getitem__(self, id):
		# XXX reading log entries don't have a key
		return Entry(self.entries_dir, id)
	
	def __iter__(self):
		return chain(
				(Entry(self.entries_dir, filename) 
				 for filename in os.listdir(self.entries_dir)
				 if not filename.startswith('.')), 
				(ReadingLogEntry(d)
				 for d in yaml.load_all(open(self.readinglog_file, 'r')))
				)

	def by_category(self):
		"""
		Returns a dict of (category -> set of entries).
		"""
		d = {}
		for entry in self:
			for category in entry.categories:
				d.setdefault(category, set()).add(entry)
		return d

	def categories(self):
		"""
		Returns a frequency-ordered list of categories.
		"""
		by_category = self.by_category()
		return sorted(by_category.iterkeys(), 
				key=lambda c: len(by_category[c]), 
				reverse=True)

	def by_tag(self):
		d = {}
		for entry in self:
			for tag in entry.tags:
				d.setdefault(tag, set()).add(entry)
		return d


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
		md = markdown.Markdown(extensions=['meta', 'typography'])
		self.body = genshi.Markup(md.convert(self.raw))
		self.metadata = cleanup_metadata(md.Meta)
		self.title = mini_markdown(self.metadata['title'])

		raw_cats = self.metadata.get('categories', '').strip()
		if raw_cats:
			self.categories = frozenset(cat.strip() for cat in raw_cats.split(','))
		else:
			self.categories = frozenset()
		raw_tags = self.metadata.get('tags', '').strip()
		if raw_tags:
			self.tags = frozenset(tag.strip() for tag in raw_tags.split(','))
		else:
			self.tags = frozenset()

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


class ReadingLogEntry(object):

	def __init__(self, yaml_dict):
		self.title = mini_markdown(yaml_dict['Title'])
		self.author = yaml_dict['Author']
		self.publication_date = self.modified_date = self.date = yaml_dict['Date']
		self.url = yaml_dict.get('URL', None)
		self.rating = yaml_dict.get('Rating', None)
		self.categories = frozenset([u'Reading'])
		self.tags = frozenset()

	def has_comments(self):
		return False


class Comments(object):

	def __init__(self, path):
		self.path = path
	
	def __contains__(self, id):
		return os.path.exists(os.path.join(self.path, id))

	def __len__(self):
		return count(filename 
				for filename in os.listdir(self.path) 
				if not filename.startswith('.'))
	
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
		md = markdown.Markdown(extensions=['meta', 'typography'])
		self.body = md.convert(self.raw)
		if not hasattr(md, 'Meta'): raise Exception(self.raw)
		self.metadata = md.Meta
		
		self.author = self.metadata.get('from', None)
		self.author_url = self.metadata.get('author-url', None)
		self.date = datetime.fromtimestamp(os.path.getmtime(path))

	def author_name(self):
		return self.author or u'Anonymous'
