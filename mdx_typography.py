
# from Joachim Schipper <joachim@joachimschipper.nl>
# XXX license?

"""
This is a port of a small subset of John Gruber's SmartyPants
(http://daringfireball.net/projects/smartypants/). It is compatible in the
sense that it does not do anything that SmartyPants would not; however,
SmartyPants tries to be considerably more intelligent, at the price of added
complexity and (very rarely!) getting it wrong.

This extension for Markdown performs the following translations of character
sequences into entities (controlled by config['rules']):
- ', '' and " into ``curly'' HTML quotes
- -- and --- into en- and em-dashes
- ... into an ellipsis

It also marks all-caps words with <span class=mark>. This includes THIS,
T.H.I.S. and even T0H0I0S0, but not T H I S. Set config['caps_re'] to None to
disable, or to any regular expression to change what is matched. Any text
'below' a <code> or <pre> tag is left alone (see config['caps_illegal_tags']).

Finally, it prevents
widows.

Set config['no_widows'] to False to suppress this last behaviour.

Each of these may be prevented by \\-escaping the relevant character(s) (but
note that the second ' in \\'' will still be treated, etc.)
"""
# XXX Integrate with mdx_parser.py?

import markdown
import re

class TypographyPattern(markdown.Pattern):
	def __init__(self, pattern, replace):
		# Note: markdown.Pattern uses greedy matching for the first part
		self.compiled_re = re.compile("^(.*?)%s(.*)$" % pattern, re.DOTALL)
		self.replace = tuple([(re.compile(p[0]), p[1]) for p in replace])
	
	def getCompiledRegExp(self):
		return self.compiled_re

	def handleMatch(self, m, doc):
		matched = m.group(2)

		for p, r in self.replace:
			if p.match(matched):
				return doc.createEntityReference(r)
		
		assert(('Configuration error: %s, matched by %s, must be matched by any of %s' % (matched, self.compiled_re.pattern, [p[0].pattern for p in self.replace])) == True)

class CapsPostprocessor(markdown.Postprocessor):
	def __init__(self, config):
		self.config = config

	def run(self, doc):
		elts = doc.find(lambda elt: elt.type == 'text' and self.config['caps_re'].search(elt.value))

		while elts:
			t = elts.pop()

			m = self.config['caps_re'].search(t.value)
			if not m:
				continue

			p = t.parent
			done = False
			while p != doc.documentElement:
				if p.type == 'element' and p.nodeName in self.config['caps_illegal_tags']:
					done = True
					break

				p = p.parent

			if done:
				continue

			span = doc.createElement('span')
			span.setAttribute('class', 'caps')
			span.appendChild(doc.createTextNode(m.group(1)))
			rest = doc.createTextNode(t.value[m.end():])
			
			idx = t.parent.childNodes.index(t) + 1

			t.parent.insertChild(idx, rest)
			t.parent.insertChild(idx, span)
			t.value = t.value[:m.start()]

			elts.append(rest)

class WidowsPostprocessor(markdown.Postprocessor):
	def __init__(self, config):
		self.config = config
	
	def run(self, doc):
		"""Prevent widows by turning the last piece of whitespace into
		&nbsp;"""

		elts = doc.find(lambda elt: elt.type == 'element' and elt.nodeName == 'p')

		for p in elts:
			texts = p.find(lambda elt: elt.type == 'text')

			while texts:
				t = texts.pop()

				idx = max(t.value.rfind(' '), t.value.rfind('\n'))

				if idx != -1:
					# Replace by &nbsp;
					rest = doc.createTextNode(t.value[:idx])
					t.value = t.value[idx + 1:]

					idx = t.parent.childNodes.index(t)

					t.parent.insertChild(idx, doc.createEntityReference('nbsp'))
					t.parent.insertChild(idx, rest)

					break

class TypographyExtension(markdown.Extension):
	def __init__(self, config):
		self.config = config
	
	def extendMarkdown(self, md, md_globals):
		idx = md.inlinePatterns.index(markdown.STRONG_EM_PATTERN)

		rules = self.config['rules']
		rules.reverse()
		for (opening_regex, rules) in rules:
			md.inlinePatterns.insert(idx, TypographyPattern(opening_regex, rules))

		if self.config['caps_re']:
			md.postprocessors.append(CapsPostprocessor(self.config))
		if self.config['no_widows']:
			md.postprocessors.append(WidowsPostprocessor(self.config))

def makeExtension(config=[]):
	if not config:
		config = {}
	if not config.has_key('rules'):
		config['rules'] = [(r'(---?|\.\.\.)',      # apply rule to this
		                    (('---', 'mdash'),     # (regex, entity)
		                     ('--', 'ndash'),
		                     ('\.\.\.', '#8230'))),# end of rule
		                   (r"\B(\"|''?)\b",
		                    (("\"|''", 'ldquo'),
		                     ("'", 'lsquo'))),
				   (r"(?:\b|(?<=[,.!?]))(\"|''?)",
		                    (("\"|''", 'rdquo'),
		                     ("'", 'rsquo')))]
	if not config.has_key('no_widows'):
		config['no_widows'] = False
	if not config.has_key('caps_re'):
		config['caps_re'] = r'\b([0-9]*(?:[A-Z][0-9]*){2,}|(?:[A-Z]\.){2,})(?=\b|[ ,.!?-])'
	if not config.has_key('caps_illegal_tags'):
		config['caps_illegal_tags'] = ['code', 'pre']

	#config['caps_re'] = re.compile(config['caps_re'])
	config['caps_re'] = None

	return TypographyExtension(config)
