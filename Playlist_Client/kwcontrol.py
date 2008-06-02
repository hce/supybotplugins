#!/usr/bin/env python

import kwunderlich

AUTHPASSWORD = 'REGSsg!9#(@fooBPAssfuckingPhraseChangeThisSoon'
HOST = 'salato.hcesperer.org'
PORT = 1723

c = kwunderlich.KWClient((HOST, PORT), AUTHPASSWORD)

wtf = {True:  'The operation was successful',
       False: 'Something went wrong'}

class Functions:
    def TOOL_gettopic(self, args):
        topic = c.gettopic()
        print 'The current topic is %s' % repr(topic)
    def TOOL_settopic(self, args):
        newtopic = " ".join(args)
        success = c.settopic(newtopic)
        if success: print 'Successfully set the topic to %s' % repr(newtopic)
        else: print wtf[success]
    def TOOL_play(self, args):
        what = " ".join(args)
        try: [album, title] = [i.strip() for i in what.split(",", 1)]
        except:
            print 'Arguments: ALBUM, TITLE'
            return
        success = c.activate(album, title)
        print wtf[success]
    def TOOL_finish(self, args):
        print wtf[c.finish()]


fcts = Functions()
fcdct = Functions.__dict__

import sys
function = sys.argv[0]
function = 'TOOL_' + function.split('/')[-1]
if len(sys.argv) > 1: parms = sys.argv[1:]
else: parms = []
if not function in fcdct: print 'function %s does not exist' % (function)
else:
    fcdct[function].__call__(fcts, parms)
    
