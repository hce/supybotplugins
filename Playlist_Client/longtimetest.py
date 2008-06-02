#!/usr/bin/env python

import kwunderlich
import sys
from time import sleep

AUTHPASSWORD = 'REGSsg!9#(@fooBPAssfuckingPhraseChangeThisSoon'
HOST = 'salato.hcesperer.org'
PORT = 1723

print 'running long-time test...'

c = kwunderlich.KWClient((HOST, PORT), AUTHPASSWORD)

class ChanOp:
    def __init__(self, nick):
        self.nick = nick

def MakeSpace(cl, len):
    if cl >= len: return ''
    return ''.join([' ' for i in range(len - cl)])

curtopic = ''
ops = {}
while True:
    topic = c.gettopic()
    if topic != curtopic:
        print 'Topic changed to: %s' % topic
        curtopic = topic
    newops = c.getops()
    for op in newops:
        if op not in ops:
            space = MakeSpace(len(op), 17)
            print ' * %s %sis now a channel operator' % (op, space)
            ops[op] = ChanOp(op)
    for op in ops:
        if op not in newops:
            space = MakeSpace(len(op), 17)
            print ' * %s %sis no longer a channel operator' % (op, space)
            del ops[op]
    print '---MARK---'
    try: sleep(120)
    except KeyboardException, e: sys.exit(0) 
