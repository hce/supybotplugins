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

import time
import threading

class FeedReader(threading.Thread):
    def __init__(self, plugin):
        threading.Thread.__init__(self)
        self.plugin = plugin
        self.events = []
        self.RSSURL = ("mrmcd110b.metarheinmain.de", '/fahrplan/schedule.en.xcs')
        self.REFRESH_INTERVAL = 60 # 60 s; should be something like 1800 for production use probably...
        self.ANNOUNCETIME = 60 # announce 60s prior to event
        self.ANNOUNCEMESSAGE = """==> Gleich fuer euch auf den mrmcds: %(pentabarf:title)s von %(attendee)s
==> %(summary)s
==> Diese Veranstaltung findet in Raum %(location)s statt. Dauer: %(duration)s
<== END OF DETAILS FOR THIS VERANSTALTUNG ==="""
        self.ANNOUNCECHANNEL = '#mrmcd111b'
    def DoRefresh(self):
        xcal = xcalparser.XCal(self.RSSURL)
        newevents = [e for e in xcal.GetPostTimeEvents(time.time()) if e not in self.events]
        n = len(newevents)
        if n:
            print 'Added %d new events.' % n
            self.events = self.events + newevents
    def run(self):
        self.next_refresh = 0
        while True:
            time.sleep(10)
            if time.time() > self.next_refresh:
                self.DoRefresh()
                self.next_refresh = time.time() + self.REFRESH_INTERVAL
            while True:
                try: atime, event = self.events[0]
                except: break
                if time.time() > (atime - self.ANNOUNCETIME):
                    amsg = self.ANNOUNCEMESSAGE % event.dict()
                    for aline in amsg.split("\n"):
                        tmsg = privmsg(self.ANNOUNCECHANNEL, aline)
                        self.plugin.irc.queueMsg(tmsg)
                del self.events[0]
                time.sleep(10)


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


Class = Xcal


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=1024:
