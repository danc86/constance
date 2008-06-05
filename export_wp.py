import os, time
import MySQLdb

cn = MySQLdb.connect(host='cruz', user='root', passwd='ELIDED', db='wordpress')

cur = cn.cursor()
cur.execute('SELECT post_name, post_title, post_date, post_modified, guid, post_content FROM wp_posts WHERE post_status = "publish"')
for row in cur.fetchall():
    post_name, post_title, post_date, post_modified, guid, post_content = row
    os.mkdir(post_name)
    f = open(os.path.join(post_name, 'content.txt'), 'w')
    f.write('Title: %s\n' % post_title)
    f.write('Publication-date: %s\n' % post_date.strftime('%Y-%m-%d %H:%M:%S'))
    f.write('Guid: %s\n' % guid)
    #f.write('Categories: %s\n' % XXX)
    #f.write('Tags: %s\n' % XXX)
    f.write('\n')
    f.write(post_content)
    del f
    os.utime(os.path.join(post_name, 'content.txt'), 
            (time.mktime(post_modified.timetuple()), time.mktime(post_modified.timetuple())))
