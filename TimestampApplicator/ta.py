# $Id$
from time import ctime as foo
from sys import argv
class SysException(Exception): pass
def die(reason): raise SysException({'usage': "Usage: SCRIPT <logfile>", 'open': "File not found"}[reason])
beginning = -1
PREFIX = 'c-radar-2008-06'
try:
    try: [me, fn] = argv
    except: die('usage')
    what = {'M': "PLAY", 'S': "STOP"}
    try: lines = open(fn, 'r').read().split("\n")
    except: die('open')
    tstamps = []
    tcmds = []
    p = None
    for l in lines:
        try: T, t, d = l.split(" ", 2)
        except: continue
        if T == 'M' or T == 'S':
            d, t = eval(d), int(t)
            print "[%s] %s: %s von %s" % (what[T], foo(t), d['title'], d['album'])
        if T == 'M':
            if d['title'] == 'warteschleife': beginning = t
            if beginning == -1: continue
            tsdiff = t - beginning
            mins, secs = int(tsdiff / 60), tsdiff % 60
            if p != None:
                tstamps.append('%d.%d' % (mins, secs))
                fn = "%s_%03d.%02d_%03d.%02d.mp3" % (PREFIX, p[0], p[1], mins, secs)
                tcmds.append('mp3info -t "%s" -a "%s" %s' % (p[2]['title'], p[2]['album'], fn))
            p = (mins, secs, d)

    print ' '.join(tstamps)
    print "\n".join(tcmds)

except SysException, e: print "Error: %s" % e

