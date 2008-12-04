import re, urllib
from markdown2 import Markdown
import genshi

def markdown(s, safe_mode=None):
    m = Markdown(extras=['code_friendly'], safe_mode=safe_mode).convert(s)
    return genshi.Markup(m)

def mini_markdown(s, safe_mode=None):
    # XXX find a more efficient way to do this?
    m = Markdown(extras=['code_friendly']).convert(s)
    match = re.match(u'<p>(.*)</p>', m)
    assert match, m
    return genshi.Markup(match.group(1))

IDIFY_WHITESPACE_PATT = re.compile(r'(?u)\s+')
IDIFY_ACCEPT_PATT = re.compile(r'(?u)\w|[-_]')
def idify(s):
    # http://www.w3.org/TR/REC-xml/#NT-Name
    s = s.lower()
    s = IDIFY_WHITESPACE_PATT.sub(u'-', s)
    return u''.join(c for c in s if IDIFY_ACCEPT_PATT.match(c))

ATOM_TIME_FORMAT = '%Y-%m-%dT%H:%M:%S+10:00'

def tag_list(script_name, tags):
    # XXX urllib.quote
    return genshi.Markup(u', ').join(
            genshi.Markup(u'<a rel="tag" href="%s/tags/%s">%s</a>' % (script_name, tag, tag)) 
            for tag in tags)
