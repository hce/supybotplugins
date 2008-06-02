#!/usr/bin/env python

import kwunderlich
import sys
from time import sleep

AUTHPASSWORD = 'REGSsg!9#(@fooBPAssfuckingPhraseChangeThisSoon'
HOST = 'salato.hcesperer.org'
PORT = 1723

print 'running long-time test...'

c = kwunderlich.KWClient((HOST, PORT), AUTHPASSWORD)

class ChanUser:
    def __init__(self, nick):
        self.nick = nick
class ChanOp(ChanUser): pass

def MakeSpace(cl, len):
    if cl >= len: return ''
    return ''.join([' ' for i in range(len - cl)])

curtopic = ''
ops = {}
users = {}
while True:
    topic = c.gettopic()
    if topic != curtopic:
        print 'Topic changed to: %s' % topic
        curtopic = topic
    newops = c.getops()
    addops = []
    for op in newops:
        if op not in ops:
            space = MakeSpace(len(op), 17)
            print ' * %s %sis now a channel operator' % (op, space)
            addops.append(op)
    for op in addops: ops[op] = ChanOp(op)
    delops = []
    for op in ops:
        if op not in newops:
            space = MakeSpace(len(op), 17)
            print ' * %s %sis no longer a channel operator' % (op, space)
            delops.append(op)
    for op in delops: del ops[op]
    newusers = c.getusers()
    addusers = []
    for user in newusers:
        if user not in users:
            space = MakeSpace(len(user), 17)
            print ' * %s %sjoined #c-radar' % (user, space)
            addusers.append(user)
    for user in addusers: users[user] = ChanUser(user)
    delusers = []
    for user in users:
        if user not in newusers:
            space = MakeSpace(len(user), 17)
            print ' * %s %sleft #c-radar' % (user, space)
            delusers.append(user)
    for user in delusers: del users[user]
    print '---MARK---'
    try: sleep(120)
    except KeyboardException, e: sys.exit(0) 
