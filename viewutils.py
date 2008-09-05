import re
import markdown
import genshi

def mini_markdown(s):
    # XXX find a more efficient way to do this?
    m = markdown.Markdown(extensions=['typography']).convert(s)
    the_p, = re.match(u'<p>(.*)\n</p>', m).groups()    
    return genshi.Markup(the_p)

def tag_list(script_name, tags):
    return genshi.Markup(u', ').join(
            genshi.Markup(u'<a rel="tag" href="%s/+tags/%s">%s</a>' % (script_name, tag, tag)) 
            for tag in tags)
