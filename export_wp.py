import os, time
import MySQLdb

cn = MySQLdb.connect(host='cruz', user='root', passwd='ELIDED', db='wordpress')

cur = cn.cursor()
cur.execute('SELECT id, post_name, post_title, post_date, post_modified, guid, post_content FROM wp_posts WHERE post_status = %s', ('publish',))
for row in cur.fetchall():
    id, post_name, post_title, post_date, post_modified, guid, post_content = row
    subcur = cn.cursor()
    subcur.execute('SELECT wp_terms.name FROM wp_term_relationships INNER JOIN wp_term_taxonomy ON wp_term_relationships.term_taxonomy_id = wp_term_taxonomy.term_taxonomy_id INNER JOIN wp_terms ON wp_term_taxonomy.term_id = wp_terms.term_id WHERE taxonomy = %s AND object_id = %s', ('category', id,))
    categories = [category for category, in subcur.fetchall()]
    subcur = cn.cursor()
    subcur.execute('SELECT wp_terms.name FROM wp_term_relationships INNER JOIN wp_term_taxonomy ON wp_term_relationships.term_taxonomy_id = wp_term_taxonomy.term_taxonomy_id INNER JOIN wp_terms ON wp_term_taxonomy.term_id = wp_terms.term_id WHERE taxonomy = %s AND object_id = %s', ('post_tag', id,))
    tags = [tag for tag, in subcur.fetchall()]

    os.mkdir(post_name)
    f = open(os.path.join(post_name, 'content.txt'), 'w')
    f.write('Title: %s\n' % post_title)
    f.write('Publication-date: %s\n' % post_date.strftime('%Y-%m-%d %H:%M:%S'))
    f.write('Guid: %s\n' % guid)
    f.write('Categories: %s\n' % ', '.join(categories))
    f.write('Tags: %s\n' % ', '.join(tags))
    f.write('\n')
    f.write(post_content)
    del f
    os.utime(os.path.join(post_name, 'content.txt'), 
            (time.mktime(post_modified.timetuple()), time.mktime(post_modified.timetuple())))
