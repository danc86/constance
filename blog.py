import os, re, uuid, email
from datetime import datetime
import genshi
import yaml


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

IDIFY_WHITESPACE_PATT = re.compile(r'(?u)\s+')
IDIFY_ACCEPT_PATT = re.compile(r'(?u)\w|[-_]')
def idify(s):
    # http://www.w3.org/TR/REC-xml/#NT-Name
    s = s.lower()
    s = IDIFY_WHITESPACE_PATT.sub(u'-', s)
    return u''.join(c for c in s if IDIFY_ACCEPT_PATT.match(c))


class EntryNotFoundError(ValueError): pass

class EntryForbiddenError(ValueError): pass

class CommentingForbiddenError(ValueError): pass # XXX why all the different types?

class CommentNotFoundError(ValueError): pass

class CommentForbiddenError(ValueError): pass


class DirectoryEntrySet(object):

    def __init__(self, base_dir):
        self.base_dir = base_dir
        assert os.path.isdir(self.base_dir), self.base_dir

    def __contains__(self, key):
        return os.path.exists(os.path.join(self.base_dir, key))

    def __getitem__(self, key):
        if key not in self: raise KeyError(key)
        return self.entry_class(self.base_dir, key)

    def __len__(self):
        return count(filename 
                for filename in os.listdir(self.base_dir) 
                if not filename.startswith('.'))

    def __iter__(self):
        assert isinstance(self.base_dir, str)
        return (self.entry_class(self.base_dir, filename)
                for filename in os.listdir(self.base_dir)
                if not filename.startswith('.'))


class YamlEntrySet(object):

    def __init__(self, filename):
        self.filename = filename
        assert os.path.isfile(self.filename), self.filename

    def __iter__(self):
        return (self.entry_class(d)
                for d in yaml.load_all(open(self.filename, 'r')))


class BlogEntry(object):

    def __init__(self, entries_dir, id):
        assert isinstance(id, str), id
        self.id = id.decode('utf8') # XXX shouldn't hardcode the encoding
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


class BlogEntrySet(DirectoryEntrySet):

    entry_class = BlogEntry


class ReadingLogEntry(object):

    def __init__(self, yaml_dict):
        self.title = yaml_dict['Title']
        self.id = idify(self.title)
        self.author = yaml_dict['Author']
        self.publication_date = self.modified_date = self.date = yaml_dict['Date']
        self.url = yaml_dict.get('URL', None)
        self.isbn = yaml_dict.get('ISBN', None)
        self.rating = yaml_dict.get('Rating', None)
        self.tags = frozenset()
        self.guid = yaml_dict['GUID']

    def has_comments(self):
        return False


class ReadingLogEntrySet(YamlEntrySet):

    entry_class = ReadingLogEntry


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


class CommentSet(DirectoryEntrySet):

    entry_class = Comment
