# $Id$
from time import ctime as foo
from sys import argv
class SysException(Exception): pass
def die(reason): raise SysException({'usage': "Usage: SCRIPT <logfile>", 'open': "File not found"}[reason])
beginning = -1
try:
    try: [me, fn] = argv
    except: die('usage')
    what = {'M': "PLAY", 'S': "STOP"}
    try: lines = open(fn, 'r').read().split("\n")
    except: die('open')
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
            print tsdiff
            mins, secs = int(tsdiff / 60), tsdiff % 60
            print '%d:%d' % (mins, secs)

except SysException, e: print "Error: %s" % e

