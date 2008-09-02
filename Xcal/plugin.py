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
import re
from random import random

import xcalparser

import time as modtime
import threading

diff = modtime.time() - modtime.mktime((2008,9,6,16,49,00,0,196,1))

durationfoo = re.compile("([0-9]+)H([0-9]+)M([0-9]+)S")
locationfoo = re.compile("([A-E][0-9]{3})")

def niceduration(duration):
    try:
        [hrs, mins, secs] = [int(foo) for foo in durationfoo.search(duration).groups()]
        s = []
        if hrs != 0:
            if hrs == 1: s.append("Eine Stunde")
            else: s.append("%s Stunden" % hrs)
        if mins != 0:
            if mins == 1: s.append("eine Minute")
            else: s.append("%d Minuten" % mins)
        if secs != 0:
            if secs == 1: s.append("eine Sekunde")
            else: s.append("%d Sekunden" % secs)
        if len(s) == 1: return s[0]
        elif len(s) == 2: return " und ".join(s)
        else: return "%s, %s und %s" % tuple(s)
    except: return duration

# eher darmstaedter dialekt
hessisch = {
    '==> Gleich fuer euch auf den mrmcds': "Owwacht gewwe! Gleisch fier eisch uff de mrmcds",
    " von ": " vomm ",
    "Diese Veranstaltung findet ": "Dess tut ",
    " statt": " stattfinne",
    "in Raum": "imm Zimma",
    "Beginn:": "Oofange tut des umm",
    "; Dauer:": " unn dauert",
    "Eine": "aa",
    "Stunden": "Stunne",
    "Stunde": "Stunn",
    "Minuten": "Minute",
    "Sekunden": "Sekunde",
    "im Workshopraum": "bei de worschdler",
    "auf der Musicstage": "uff de WET-Staittsch",
    "in einem VPN": "innem faupeenn",
    "im Freien": "inner freie Nadur",
    " 2 ": " zwaa ",
    " 30 ": " dreisisch ",
    " und ": " unn ",
    " 3 ": " drei ",
    " 4 ": " vier ",
    " 5 ": " fuenf ",
    " 6 ": " sexx ",
    " 7 ": " sibbe ",
    " 8 ": " acht ",
    " 9 ": " nein ",
    " 10 ": " zehe ",
}

def tohessisch(hochteutsch):
    for k in hessisch: hochteutsch = hochteutsch.replace(k, hessisch[k])
    return hochteutsch

def makeloc(foo):
    bar = locationfoo.search(foo)
    if bar != None:
        return 'in Raum %s' % bar.groups()[0]
    try: return {'workshop': 'im Workshopraum',
            'outdoor': 'im Freien',
            'contest': 'in einem VPN',
            'musicstage': 'auf der Musicstage'}[foo.strip().lower()]
    except: return 'im/auf/bei/als/foo "%s"' % foo

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
        self.RSSURL = ("www.hcesperer.org", '/temp/mrmcdtmp.txt')
        self.REFRESH_INTERVAL = 1800 # 30 mins
        self.ANNOUNCETIME = 600 # 10 mins
        self.ANNOUNCEMESSAGE = """==> Gleich fuer euch auf den mrmcds: %(pentabarf:title)s von %(attendee)s
%(summary)s
Diese Veranstaltung findet %(location)s statt.
Beginn: %(begintime)s; Dauer: %(duration)s""".replace("\n", " -- ")
        self.ANNOUNCECHANNEL = '#mrmcd111b-bot'
    def DoRefresh(self):
        try:
            xcal = xcalparser.XCal(self.RSSURL)
            newevents = [e for e in xcal.GetPostTimeEvents(time()) if e[1].get('uid') not in self.uids]
            for event in newevents: self.uids.append(event[1].get('uid'))
            n = len(newevents)
            if n:
                self.plugin.irc.queueMsg(privmsg('#mrmcd111b-bot', 'Added %d new event%s.' % (n, {True: '', False: 's'}[n == 1])))
                self.events = self.events + newevents
        except Exception, e:
            self.plugin.irc.queueMsg(privmsg('#mrmcd111b-bot', 'Error: couldn\'t update: %s' % str(e)))
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
                    edict = event.dict()
                    if not 'pentabarf:title' in edict: edict['pentabarf:title'] = "Unbenannte Veranstaltung"
                    if not 'attendee' in edict: edict['attendee'] = "Anonymous coward"
                    if not 'summary' in edict: edict['summary'] = "NO SUMMARY -- REPORT THIS AS A BUG"
                    if not 'location' in edict: edict['location'] = 'foo bar'
                    if not 'begintime' in edict: edict['begintime'] = "Keine Ahnung, wann's losgeht"
                    if not 'duration' in edict: edict['duration'] = "Zu lange"
                    edict['duration'] = niceduration(edict['duration'])
                    edict['location'] = makeloc(edict['location'])
                    amsg = self.ANNOUNCEMESSAGE % edict
                    if random() < 0.5:
                        amsg = tohessisch(amsg)
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
