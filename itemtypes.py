
"""
This module defines the various item types which are supported by Constance.

An "item" is anything which can be referenced individually by a URL and 
rendered, and/or appears in a stream of items. As a minimum each type of item 
must have the following data attached to it:

    * datetime of original publication (as the `publication_date` attribute)
    * datetime at which the content of the item was last modified (as the 
      `modified_date` attribute)
    * unique URI path within the collection (as the `uri_path` attribute)

Each item type defines a collection type whose name ends in Set (e.g. 
BlogEntrySet). The collection can be iterated across using iter(), which yields 
a sequence of item instances (if a collection does not support iteration its 
iterator yields nothing). Individual items can also be fetched from the 
collection by calling its `get` attribute with a URI path; either an item 
instance is returned, or KeyError is raised if the URI path is not known.
"""

import os, re, uuid, email
from datetime import datetime
import genshi.template
import yaml

template_loader = genshi.template.TemplateLoader(
        os.path.join(os.path.dirname(__file__), 'templates'), 
        variable_lookup='strict', 
        auto_reload=True)

__all__ = ['NoAccessError', 'NotExistError', 'UnsupportedFormatError', 
           'BlogEntrySet', 'ReadingLogEntrySet']

def count(iterable):
    count = 0
    for _ in iterable:
        count += 1
    return count

def cleanup_metadata(header_items):
    cleaned = {}
    for k, v in header_items:
        k = k.lower()
        if k.endswith('date'):
            v = datetime.strptime(v, '%Y-%m-%d %H:%M:%S')
        else:
            v = v.decode('utf8') # XXX encoding
        cleaned[k] = v
    return cleaned


class NoAccessError(StandardError): pass

class NotExistError(StandardError): pass

class UnsupportedFormatError(StandardError): pass


class BlogEntry(object):

    def __init__(self, entries_dir, id, uri_path):
        assert isinstance(id, str), id
        self.id = id.decode('utf8') # XXX shouldn't hardcode the encoding
        self.uri_path = uri_path
        self.dir = os.path.join(entries_dir, id)
        self.comments_dir = os.path.join(self.dir, 'comments')

        if not os.path.exists(self.dir):
            raise EntryNotFoundError()
        if not os.access(self.dir, os.R_OK):
            raise EntryForbiddenError()

        # not really a MIME document, but parse it like one
        msg = email.message_from_file(open(os.path.join(self.dir, 'content.txt'), 'r'))
        self.metadata = cleanup_metadata(msg.items())
        self.body = msg.get_payload().decode('utf8') # XXX encoding
        self.title = self.metadata['title']

        raw_tags = self.metadata.get('tags', '').strip()
        if raw_tags:
            self.tags = frozenset(tag.strip() for tag in raw_tags.split(','))
        else:
            self.tags = frozenset()

        self.modified_date = datetime.fromtimestamp(os.path.getmtime(os.path.join(self.dir, 'content.txt')))
        self.publication_date = self.metadata.get('publication-date', None) or self.modified_date
        self.guid = self.metadata['guid']

    def render(self, format):
        if format == 'text/html':
            template = template_loader.load('html/' + self.__class__.__name__ + '.xml')
            return template.generate(item=self)
        elif format == 'application/atom+xml':
            template = template_loader.load('atom/' + self.__class__.__name__ + '.xml')
            return template.generate(item=self)
        else:
            raise UnsupportedFormatError(format)

    def comments(self):
        return CommentSet(self.comments_dir)

    def has_comments(self):
        """
        Returns True if this Entry could *possibly* have comments, although it 
        may still have no comments (yet).
        """
        return os.path.isdir(self.comments_dir) and \
                os.access(self.comments_dir, os.R_OK)

    def add_comment(self, metadata, content):
        if not os.access(self.comments_dir, os.W_OK):
            raise CommentingForbiddenError()
        # XXX write to temp file
        guid = uuid.uuid4().get_hex()
        f = open(os.path.join(self.comments_dir, guid), 'w')
        for k, v in metadata.iteritems():
            f.write('%s: %s\n' % (k, v.encode('utf8'))) # XXX encoding
        f.write('\n')
        f.write(content.encode('utf8')) # XXX encoding


class BlogEntrySet(object):

    def __init__(self, base_dir, prefix='/blog'):
        self.base_dir = base_dir
        assert os.path.isdir(self.base_dir), self.base_dir
        self.prefix = prefix
        self.index_patt = re.compile(re.escape(prefix) + r'/?(index)?$')
        self.entry_patt = re.compile(re.escape(prefix) + r'/([^/]+)/?$')

    def get(self, path_info):
        if self.index_patt.match(path_info):
            return iter(self)
        m = self.entry_patt.match(path_info)
        if m is None:
            raise NotExistError(path_info)
        id = m.group(1).encode('utf8') # XXX don't hardcode
        if not os.path.isdir(os.path.join(self.base_dir, id)):
            raise NotExistError(path_info)
        return BlogEntry(self.base_dir, id, path_info)

    def __iter__(self):
        assert isinstance(self.base_dir, str)
        return (BlogEntry(self.base_dir, filename, self.prefix + '/' + filename.decode('utf8'))
                for filename in os.listdir(self.base_dir)
                if not filename.startswith('.'))


class ReadingLogEntry(object):

    def __init__(self, yaml_dict):
        self.title = yaml_dict['Title']
        self.author = yaml_dict['Author']
        self.publication_date = self.modified_date = self.date = yaml_dict['Date']
        self.url = yaml_dict.get('URL', None)
        self.isbn = yaml_dict.get('ISBN', None)
        self.rating = yaml_dict.get('Rating', None)
        self.tags = frozenset()
        self.guid = yaml_dict['GUID']

    def render(self, format):
        if format == 'text/html':
            template = template_loader.load('html/' + self.__class__.__name__ + '.xml')
            return template.generate(item=self)
        elif format == 'application/atom+xml':
            template = template_loader.load('atom/' + self.__class__.__name__ + '.xml')
            return template.generate(item=self)
        else:
            raise UnsupportedFormatError(format)

    def has_comments(self):
        return False


class ReadingLogEntrySet(object):

    def __init__(self, filename, prefix='/reading'):
        self.filename = filename
        assert os.path.isfile(self.filename), self.filename
        self.prefix = prefix
        self.index_patt = re.compile(re.escape(prefix) + r'/?(index)?$')

    def get(self, path_info):
        if self.index_patt.match(path_info):
            return iter(self)
        raise NotExistError(path_info)

    def __iter__(self):
        return (ReadingLogEntry(d)
                for d in yaml.load_all(open(self.filename, 'r')))


class Comment(object):

    def __init__(self, comments_dir, id):
        path = os.path.join(comments_dir, id)
        if not os.path.exists(path):
            raise CommentNotFoundError()
        if not os.access(path, os.R_OK):
            raise CommentForbiddenError()

        self.id = id
        msg = email.message_from_file(open(path, 'r'))
        self.metadata = cleanup_metadata(msg.items())
        self.body = msg.get_payload().decode('utf8') # XXX encoding
        
        self.author = self.metadata.get('from', None)
        self.author_url = self.metadata.get('author-url', None)
        self.date = datetime.fromtimestamp(os.path.getmtime(path))

    def author_name(self):
        return self.author or u'Anonymous'


class CommentSet(object):

    def __init__(self, base_dir):
        self.base_dir = base_dir
        assert os.path.isdir(self.base_dir), self.base_dir

    def __len__(self):
        return count(filename 
                for filename in os.listdir(self.base_dir) 
                if not filename.startswith('.'))

    def __iter__(self):
        assert isinstance(self.base_dir, str)
        return (Comment(self.base_dir, filename)
                for filename in os.listdir(self.base_dir)
                if not filename.startswith('.'))
