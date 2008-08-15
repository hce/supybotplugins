###
# Copyright (c) 2008, Hans-Christian Esperer
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
from supybot.ircmsgs import privmsg, topic

import xcalparser

import time as modtime
import threading

diff = modtime.time() - modtime.mktime((2008,9,5,20,13,00,0,196,1))

def time():
    return modtime.time() - diff

class FeedReader(threading.Thread):
    def __init__(self, plugin):
        threading.Thread.__init__(self)
        self.plugin = plugin
        self.events = []
        self.uids = []
        self.dostop = False
        # self.RSSURL = ("mrmcd110b.metarheinmain.de", '/fahrplan/schedule.en.xcs')
        # self.RSSURL = ("www.hcesperer.org", '/temp/schedule.en.xcs')
        self.RSSURL = ("cyber-trooper.de", "/xcal/conference/59%3flanguage=en")
        self.REFRESH_INTERVAL = 1800 # 30 mins
        self.ANNOUNCETIME = 600 # 10 mins
        self.ANNOUNCEMESSAGE = """==> Gleich fuer euch auf den mrmcds: %(pentabarf:title)s von %(attendee)s
%(summary)s
Diese Veranstaltung findet in Raum %(location)s statt.
Beginn: %(begintime)s; Dauer: %(duration)s""".replace("\n", " -- ")
        self.ANNOUNCECHANNEL = '#mrmcd111b-bot'
    def DoRefresh(self):
        try:
            xcal = xcalparser.XCal(self.RSSURL)
            newevents = [e for e in xcal.GetPostTimeEvents(time()) if e[1].get('uid') not in self.uids]
            for event in newevents: self.uids.append(event[1].get('uid'))
            n = len(newevents)
            if n:
                print 'Added %d new event%s.' % (n, {True: '', False: 's'}[n == 1])
                self.events = self.events + newevents
        except Exception, e:
            print 'Error: couldn\'t update: %s' % str(e)
    def run(self):
        self.next_refresh = 0
        while not self.dostop:
            modtime.sleep(10)
            if time() > self.next_refresh:
                self.DoRefresh()
                self.next_refresh = time() + self.REFRESH_INTERVAL
            while True:
                try: atime, event = self.events[0]
                except: break
                if time() > (atime - self.ANNOUNCETIME):
                    # self.plugin.irc.queueMsg(privmsg(self.ANNOUNCECHANNEL, "Aktuelles Datum aus Sicht des Bot: %s" %
                    #         modtime.asctime(modtime.localtime(time()))))
                    amsg = self.ANNOUNCEMESSAGE % event.dict()
                    for aline in amsg.split("\n"):
                        tmsg = privmsg(self.ANNOUNCECHANNEL, aline)
                        self.plugin.irc.queueMsg(tmsg)
                    del self.events[0]
                    modtime.sleep(10)
                else: break
    def stop(self):
        self.dostop = True


class Xcal(callbacks.Plugin):
    """Add the help for "@plugin help Xcal" here
    This should describe *how* to use this plugin."""
    threaded = True

    def __init__(self, irc):
        self.__parent = super(Xcal, self)
        self.__parent.__init__(irc)
        self.irc = irc
        self.feedreader = FeedReader(self)
        self.feedreader.setDaemon(True)
        self.feedreader.start()
    def die(self):
        self.feedreader.stop()


Class = Xcal


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=1024:
