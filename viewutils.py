import re
import markdown
import genshi

import config

def mini_markdown(s):
    # XXX find a more efficient way to do this?
    m = markdown.Markdown(extensions=['typography']).convert(s)
    the_p, = re.match(u'<p>(.*)\n</p>', m).groups()    
    return genshi.Markup(the_p)

def category_list(categories):
    return genshi.Markup(u', ').join(
            genshi.Markup(u'<a href="%s/+categories/%s">%s</a>' % (config.REL_BASE, category, category)) 
            for category in categories)

def tag_list(tags):
    return genshi.Markup(u', ').join(
            genshi.Markup(u'<a rel="tag" href="%s/+tags/%s">%s</a>' % (config.REL_BASE, tag, tag)) 
            for tag in tags)
