import os, time, re, urllib, uuid, sys
import MySQLdb
import yaml

def export(options):
    log_entries = []

    cn = MySQLdb.connect(host=options.host, user=options.username, 
            passwd=options.password, db=options.db, use_unicode=True)

    cur = cn.cursor()
    cur.execute('SELECT id, post_title, post_date, guid FROM wp_posts '
            'INNER JOIN wp_term_relationships ON '
            'wp_term_relationships.object_id = wp_posts.id '
            'WHERE post_status = %s AND term_taxonomy_id = %s '
            'ORDER BY post_date ASC', ('publish', 14))
    for row in cur.fetchall():
        id, title, date, guid = row
        entry = {'Title': title, 'Date': date, 'GUID': guid}
        subcur = cn.cursor()
        subcur.execute('SELECT meta_key, meta_value FROM wp_postmeta '
                'WHERE post_id = %s', (id,))
        for key, value in subcur.fetchall():
            if key == '_readinglog_url': entry['URL'] = value
            elif key == '_readinglog_author': entry['Author'] = value
            elif key == '_readinglog_rating': entry['Rating'] = float(value)
        log_entries.append(entry)

    if options.output is not None:
        f = open(options.output, 'w')
    else:
        f = sys.stdout
    
    yaml.add_representer(unicode, lambda dumper, value: 
            dumper.represent_scalar(u'tag:yaml.org,2002:str', value))
    yaml.dump_all(log_entries, f, default_flow_style=False, allow_unicode=True)

if __name__ == '__main__':
    from optparse import OptionParser
    parser = OptionParser()
    parser.add_option('-H', '--host', 
            help='connect to MySQL server HOST [default: %default]')
    parser.add_option('-u', '--username', 
            help='use USERNAME when connecting [default: %default]')
    parser.add_option('-p', '--password', 
            help='use PASSWORD when connecting [default: no password]')
    parser.add_option('-d', '--db', 
            help='name of the Wordpress database [default: %default]')
    parser.set_defaults(host='localhost', username='root', 
            password=None, db='wordpress')
    parser.add_option('-o', '--output', metavar='FILE', 
            help='write output to FILE instead of stdout')
    options, args = parser.parse_args()
    export(options)
