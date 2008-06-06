import os, time, re, urllib, uuid
import MySQLdb

def html2md(s):
	s = s.replace('<p>', '')
	s = s.replace('</p>', '')
	# XXX
	return s

def export(base_dir):
	if not os.path.exists(base_dir):
		os.mkdir(base_dir)

	cn = MySQLdb.connect(host='cruz', user='root', passwd='ELIDED', db='wordpress')

	cur = cn.cursor()
	cur.execute('SELECT id, post_name, post_title, post_date, post_modified, guid, post_content FROM wp_posts WHERE post_status = %s', ('publish',))
	for row in cur.fetchall():
		id, post_name, post_title, post_date, post_modified, guid, post_content = row
		
		# Wordpress stores these URL-encoded
		post_name = urllib.unquote(post_name)
		guid = urllib.unquote(guid)

		subcur = cn.cursor()
		subcur.execute('SELECT wp_terms.name FROM wp_term_relationships INNER JOIN wp_term_taxonomy ON wp_term_relationships.term_taxonomy_id = wp_term_taxonomy.term_taxonomy_id INNER JOIN wp_terms ON wp_term_taxonomy.term_id = wp_terms.term_id WHERE taxonomy = %s AND object_id = %s', ('category', id,))
		categories = [category for category, in subcur.fetchall()]
		subcur = cn.cursor()
		subcur.execute('SELECT wp_terms.name FROM wp_term_relationships INNER JOIN wp_term_taxonomy ON wp_term_relationships.term_taxonomy_id = wp_term_taxonomy.term_taxonomy_id INNER JOIN wp_terms ON wp_term_taxonomy.term_id = wp_terms.term_id WHERE taxonomy = %s AND object_id = %s', ('post_tag', id,))
		tags = [tag for tag, in subcur.fetchall()]

		os.mkdir(os.path.join(base_dir, post_name))
		f = open(os.path.join(base_dir, post_name, 'content.txt'), 'w')
		f.write('Title: %s\n' % post_title)
		f.write('Publication-Date: %s\n' % post_date.strftime('%Y-%m-%d %H:%M:%S'))
		f.write('GUID: %s\n' % guid)
		f.write('Categories: %s\n' % ', '.join(categories))
		f.write('Tags: %s\n' % ', '.join(tags))
		f.write('\n')
		f.write(post_content)
		del f
		os.utime(os.path.join(base_dir, post_name, 'content.txt'), 
				(time.mktime(post_modified.timetuple()), time.mktime(post_modified.timetuple())))

		# comments
		subcur = cn.cursor()
		subcur.execute('SELECT comment_author, comment_author_email, comment_author_url, comment_author_ip, comment_date, comment_agent, comment_content FROM wp_comments WHERE comment_post_id = %s AND comment_approved LIKE %s', (id, 1))
		os.mkdir(os.path.join(base_dir, post_name, 'comments'))
		# XXX dir perms
		for subrow in subcur.fetchall():
			author, email, url, ip_addr, date, user_agent, content = subrow
			id = str(uuid.uuid4()).replace('-', '')
			filename = os.path.join(base_dir, post_name, 'comments', id)
			f = open(filename, 'w')
			if author:
				f.write('From: %s\n' % author)
			if email:
				f.write('Author-Email: %s\n' % email)
			if url:
				f.write('Author-URL: %s\n' % url)
			if user_agent:
				f.write('User-Agent: %s\n' % user_agent)
			if ip_addr:
				f.write('Received: from %s\n' % ip_addr)
			f.write('\n')
			f.write(html2md(content)) # Wordpress HTMLifies comments >_<
			del f
			os.utime(filename, 
					(time.mktime(date.timetuple()), time.mktime(date.timetuple())))

if __name__ == '__main__':
	import sys
	export(sys.argv[1])
