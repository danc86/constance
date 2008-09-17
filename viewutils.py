import re
from markdown2 import Markdown
import genshi

def mini_markdown(s):
    # XXX find a more efficient way to do this?
    m = Markdown(extras=['code_friendly']).convert(s)
    match = re.match(u'<p>(.*)</p>', m)
    assert match, m
    return genshi.Markup(match.group(1))

def tag_list(script_name, tags):
    return genshi.Markup(u', ').join(
            genshi.Markup(u'<a rel="tag" href="%s/+tags/%s">%s</a>' % (script_name, tag, tag)) 
            for tag in tags)
