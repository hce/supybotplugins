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
import supybot.conf as conf
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.registry as registry
from supybot.ircmsgs import privmsg, topic
import re
from random import random

import xcalparser

import time as modtime
import urllib
import threading
import sys

diff = 0
# diff = modtime.time() - modtime.mktime((2008,9,6,9,49,58,0,196,1))

durationfoo = re.compile("([0-9]+)H([0-9]+)M([0-9]+)S")
locationfoo = re.compile("([A-E][0-9]{3})")

ANNOUNCEMESSAGE = """==> Upcoming event at the %(eventname)s: %(pentabarf:title)s von %(attendee)s
%(summary)s
This event takes place %(location)s.
Start: %(begintime)s; Duration: %(duration)s""".replace("\n", " -- ")

def getEventName(irc, msg, args, state):
    if not registry.isValidRegistryName(args[0]):
        state.errorInvalid('event name', args[0],
                           'Illegal event name')
    state.args.append(callbacks.canonicalName(args.pop(0)))
addConverter('eventName', getEventName)

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

def time():
    return modtime.time() - diff

class XCalStuff:
    def __init__(self):
        self.stopped = True
        self.xcal = None
        self.oldxml = ""
        self.uids = []
        self.events = []
        self.nextrefresh = 0

class FeedReader(threading.Thread):
    def __init__(self, plugin):
        threading.Thread.__init__(self)
        self.plugin = plugin
        self.log = plugin.log  # convenience reference
        self.xcals = {}
        self.dostop = False
        # channel/nick, Event name, refresh interval, announcetime, xcal URL, announce message
        self.locations = {'workshop': 'im Workshopraum',
                'outdoor': 'im Freien',
                'contest': 'in einem VPN',
                'musicstage': 'auf der Musicstage'}
        #self.events = {'mrmcd': ("#mrmcd111b", "MRMCDs", 180, 600, "http://www.hcesperer.org/temp/mrmcdtmp.txt", ANNOUNCEMESSAGE)}
        #self.events['oldmrmcd'] = ("#mrmcd110b", "Metarheinmain chaosdays 110b", 180, 600, "http://events.ccc.de/congress/2007/Fahrplan/schedule.en.xcs", ANNOUNCEMESSAGE)
        self.events = {}
        self.LoadSettings()
    def GetFN(self):
        pass
    def LoadSettings(self):
        # self.plugin.AddEvent("event", "ename", "eurl", 123, 456, "#echan", "emsg")
        # self.plugin.AddEvent("mrmcd111b", "Metarheinmain ChaosDays 111b", "http://www.hcesperer.org/temp/mrmcdtmp.txt", 180, 600, "#mrmcd111b", ANNOUNCEMESSAGE)
        events = self.plugin.registryValue("events")# , value=False).getValues(False)
        for event in events:
            self.plugin.registryValue("events").add(event)
            group = self.plugin.registryValue("events", value=False)
            subgroup = group.register(event)
            R_STRING = lambda: registry.String('', '', False)
            R_INT = lambda: registry.Integer(0, '', False)
            for datatype, value in [(R_STRING, 'title'),
                    (R_STRING, 'url'),
                    (R_INT, 'checkinterval'),
                    (R_INT, 'announcetime'),
                    (R_STRING, 'announcechannel'),
                    (R_STRING, 'announcemsg')
            ]:
                subgroup.register(value, datatype())
        events = self.plugin.registryValue("events", value=False).getValues(False)
        vkeyre = re.compile(r'\.([^\.]+)$')
        for ename, esettings in events:
            settings = esettings.getValues(False)
            ename = vkeyre.search(ename).groups()[0]
            setdict = {}
            try:
                for vkey, vname in settings:
                    try:
                        vkeyname = vkeyre.search(vkey).groups()[0]
                    except:
                        continue
                    setdict[vkeyname] = vname.value
            except Exception, e:
                self.log.warning("[%s] illegal conference settings; removing conference" % ename)
                conf.supybot.plugins.Xcal.events().remove(ename)
                conf.supybot.plugins.Xcal.events.unregister(ename)
                continue
            self.events[ename] = (
                    setdict['announcechannel'],
                    setdict['title'],
                    setdict['checkinterval'],
                    setdict['announcetime'],
                    setdict['url'],
                    setdict['announcemsg']
            )
    def DoRefresh(self, eventname):
        for event in [eventname]:
            # print 'Refreshing %s' % event
            echan, ename, erefint, eantime, eurl, emsg = self.events[event]
            stuff = self.xcals[event]
            try:
                fhttp = urllib.urlopen(eurl)
                s = fhttp.read()
                fhttp.close()
                if s == stuff.oldxml: continue
                # print 'Changes detected for %s' % event
                xcal = xcalparser.XCal(None, s)
                stuff.xcal = xcal
                stuff.oldxml = s
                # newevents = [e for e in xcal.GetPostTimeEvents(time()) if e[1].get('uid') not in self.uids]
                # for event in newevents: stuff.uids.append(event[1].get('uid'))
                newevents = xcal.GetPostTimeEvents(time())
                newevents.sort()
                stuff.uids = newevents
                n = len(newevents)
                if n:
                    msg = '[%s] reload: %d event%s.' % (ename, n, {True: '', False: 's'}[n == 1])
                    self.log.info("%s\n" % msg)
                    stuff.events = newevents
                else:
                    msg = '[%s] reload: no events. Probably lies completely in the past.' % ename
                    stuff.events = newevents
                    self.log.info("%s\n" % msg)
            except Exception, e:
                error = 'Error: couldn\'t update: %s' % str(e)
                self.log.error("%s\n" % error)
    def Makeloc(self, foo):
        bar = locationfoo.search(foo)
        if bar != None:
            return 'in room %s' % bar.groups()[0]
        try: return self.locations[foo.strip().lower()]
        except: return 'in/at/on/foo "%s"' % foo

    def run(self):
        self.next_refresh = 0
        while not self.dostop:
            # Not nice, but the supybot registry system forces us
            # to do this ;-/
            self.LoadSettings()
            for event in self.events:
                echan, ename, erefint, eantime, eurl, emsg = self.events[event]
                try:
                    stuff = self.xcals[event]
                except:
                    stuff = XCalStuff()
                    self.xcals[event] = stuff
                if time() > stuff.nextrefresh:
                    self.DoRefresh(event)
                    stuff.nextrefresh = time() + erefint
                try:
                    while True:
                        try: atime, evt = stuff.events[0]
                        except: break
                        if time() > (atime - eantime):
                            # self.plugin.irc.queueMsg(privmsg(self.ANNOUNCECHANNEL, "Aktuelles Datum aus Sicht des Bot: %s" %
                            #         modtime.asctime(modtime.localtime(time()))))
                            edict = evt.dict()
                            if not 'pentabarf:title' in edict: edict['pentabarf:title'] = "Unbenannte Veranstaltung"
                            if not 'attendee' in edict: edict['attendee'] = "Anonymous coward"
                            if not 'summary' in edict: edict['summary'] = "NO SUMMARY -- REPORT THIS AS A BUG"
                            if not 'location' in edict: edict['location'] = 'foo bar'
                            if not 'begintime' in edict: edict['begintime'] = "Keine Ahnung, wann's losgeht"
                            if not 'duration' in edict: edict['duration'] = "Zu lange"
                            edict['duration'] = niceduration(edict['duration'])
                            edict['location'] = self.Makeloc(edict['location'])
                            edict['eventname'] = ename
                            try:
                                amsg = emsg % edict
                            except Exception, e:
                                amsg = ANNOUNCEMESSAGE % edict
                                self.log.warning("[%s] Erraneous announce message; used default one. (%s)" % (event, e))
                            if random() < 0.1:
                                amsg = tohessisch(amsg)
                            for aline in amsg.split("\n"):
                                tmsg = privmsg(echan, aline)
                                self.plugin.irc.queueMsg(tmsg)
                            del stuff.events[0]
                        else: break
                except Exception, e:
                    print e
            modtime.sleep(10)
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
    def __del__(self):
        if hasattr(self.base, "__del__"):
            self.feedreader.stop()
            self.base.__del__(self)
    def AddEvent(self, ename, etitle, eurl, echeckinterval, eannouncetime, echan, emsg):
        self.registryValue("events").add(ename)
        group = self.registryValue("events", value=False)
        group.register(ename)
        sgroup = self.registryValue(registry.join(["events", ename]), value=False)
        sgroup.register('title', registry.String(etitle, ''))
        sgroup.register('url', registry.String(eurl, ''))
        sgroup.register('checkinterval', registry.Integer(echeckinterval, ''))
        sgroup.register('announcetime', registry.Integer(eannouncetime, ''))
        sgroup.register('announcechannel', registry.String(echan, ''))
        sgroup.register('announcemsg', registry.String(emsg, ''))
        self.feedreader.events[ename] = (echan, etitle, echeckinterval, eannouncetime, eurl, emsg)
    def addevent(self, irc, msg, args, ccc, channel, ename, eurl, echeckinterval, eatime, etitle):
        """addevent <channel> <eventname> <xcal feed url> <xcal check interval> <time in seconds to announce event before it takes place> <title of the converence>

        Adds a new conference.
          channel:   channel to announce conference events in
          eventname: (internal) name of the conference (no spaces)
          xcal feed: url to the xcal feed
          check intelval: in seconds. 1800 is a reasonable value.
          announcetime: how many seconds in advance to the event should it be announced? 600 is a reasonable default.
          title: public title of the conference"""
        self.AddEvent(ename, etitle, eurl, echeckinterval, eatime, channel, ANNOUNCEMESSAGE)
        irc.replySuccess()
    addevent = wrap(addevent, ['op', 'channel', 'eventName', 'url', 'positiveInt', 'positiveInt', 'text'])
                    


Class = Xcal


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=1024:
