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
from cPickle import dumps, loads, dump, load
import supybot.plugins as plugins
import supybot.world as world
import supybot.ircutils as ircutils
import supybot.callbacks as callbacks
import supybot.conf as conf
from supybot.ircmsgs import privmsg, topic

from time import time, localtime, mktime, ctime
from pprint import pformat
import os
import sys

class Playlist(callbacks.Plugin):
    """HC's  Radio playlist plugin"""

    # manually saved/loaded stuff
    sendMsg = " | now playing: "
    titleFormat = "%(title)s from %(album)s"
    nextSendung = {'#c-radar': "Details for the next show can be found at http://www.c-radar.de/"}
    miscStuff = {'#c-radar': ["http://www.c-radar.de", "fm 103,4 MHz"]}
    feedbackMsg = {'#c-radar': "The show is over; send your feedback to studio@c-radar.de"}
    msgSeparator = " | "
    pl = {'#c-radar': []}

    # transient stuff
    saved = True
    logfile = None
    playing = None
    topicAnnounced = False
    feedbackAnnounced = False

    def __init__(self, irc):
        self.__parent = super(Playlist, self)
        self.__parent.__init__(irc)
        self.flusher = self.flush
        self.irc = irc
        world.flushers.append(self.flusher)
        try: self.LoadSettings()
        except Exception, e:
            sys.stderr.write("Couldn't load settings; using defaults. (%s)" % e)
            self.saved = False

    def die(self):
        world.flushers = [x for x in world.flushers if x is not self.flusher]

    def Checkpriv(self, irc, msg, channel):
        if channel not in irc.state.channels:
            irc.error("No")
            return False
        if msg.nick not in irc.state.channels[channel].ops:
            irc.error("You can't do that thing, when you don't have that swing. (%s)" % msg.nick)
            return False
        return True

    def DataDir(self):
        dataDir = conf.supybot.directories.data.dirize(self.name())
        if not os.path.exists(dataDir): os.makedirs(dataDir)
        return dataDir

    def SaveSettings(self):
        if self.saved: return
        dd = self.DataDir() + "/globalvars.pickle"
        f = open(dd + "_tmp", 'w')
        dump(self.sendChannel, f)
        dump(self.sendMsg, f)
        dump(self.titleFormat, f)
        dump(self.nextSendung, f)
        dump(self.miscStuff, f)
        dump(self.msgSeparator, f)
        dump(self.pl, f)
        f.close()
        os.rename(dd + "_tmp", dd)
        self.saved = True

        #logDir = conf.supybot.directories.log.dirize(self.name())

    def LoadSettings(self):
        dd = self.DataDir() + "/globalvars.pickle"
        f = open(dd, 'r')
        self.sendChannel = load(f)
        self.sendMsg = load(f)
        self.titleFormat = load(f)
        self.nextSendung = load(f)
        self.miscStuff = load(f)
        self.msgSeparator = load(f)
        self.pl = load(f)
        f.close()
        self.saved = True

    def Date_FFIM(self, secs):
        dat = localtime(secs)
        while (dat[6] != 4) or (dat[2] > 7):
            secs = secs + (3600 * 24) # add one day
            dat = localtime(secs)

        dat = list(dat)
        dat[3] = 0
        dat[4] = 0
        dat[5] = 0
        dat = tuple(dat)
        
        return dat

    def Date_NextAnnouncement(self, dat):
        doa = mktime(dat)
        doa = doa - (3600 * 24 * 3) # move three days back
        return doa

    def Date_NextFeedback(self, dat):
        doa = mktime(dat)
        doa = doa + (3600 * 4) # advance four hours
        return doa

    def DoAnnouncements(self, curTime):
        nextDay = curTime + (3600 * 24)
        firstFr = self.Date_FFIM(curTime)
        aTime = self.Date_NextAnnouncement(firstFr)
        fTime = self.Date_NextFeedback(firstFr)

        #lt = ctime
        #tmsg = privmsg(self.sendChannel, "atime: %s ftime: %s nextday: %s firstdo: %s curtime: %s" % (lt(aTime), lt(fTime), lt(nextDay), lt(mktime(firstFr)), lt(curTime)))
        #self.irc.queueMsg(tmsg)
        if (aTime <= curTime) and (curTime <= nextDay) and (fTime > curTime):
            if not self.topicAnnounced:
                n_firstFr = self.Date_FFIM(curTime + 3600 * 24 * 3)
                showDate = ctime(mktime(n_firstFr) - 3600)
                mts = self.msgSeparator.join(["Next show: %s (%s)" % (self.nextSendung, showDate)] + self.miscStuff)
                tmsg = topic(self.sendChannel, mts)
                self.irc.queueMsg(tmsg)
                self.topicAnnounced = True
        elif (fTime <= curTime) and (curTime <= nextDay):
            if not self.feedbackAnnounced:
                n_firstFr = self.Date_FFIM(curTime + 3600 * 24 * 3)
                showDate = ctime(mktime(n_firstFr) - 3600)
                mts = self.msgSeparator.join([self.feedbackMsg, "Next show %s" % showDate] + self.miscStuff)
                tmsg = topic(self.sendChannel, mts)
                self.irc.queueMsg(tmsg)
                self.feedbackAnnounced = True
                self.topicAnnounced = False
        else:
            self.feedbackAnnounced = False
            self.topicAnnounced = False

    def flush(self):
        self.SaveSettings()

        # hack to call that from here...
        try: self.DoAnnouncements(time())
        except Exception, e: sys.stderr.write("Error while announcing: %s" % e)

    def NewLog(self, irc):
        logDir = conf.supybot.directories.log.dirize(self.name())
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        self.saved = False
        try:
            self.logfile = open("%s/CLOG%d.txt" % (logDir, time()), 'w')
        except Exception, e:
            irc.error("Cannot open logfile: %s" % e)
            self.logfile = sys.stderr

    def LogMessage(self, irc, msgtype, message):
        if self.logfile == None:
            self.NewLog(irc)
            if self.logfile == None:
                irc.error("Cannot log message %s" % message)
            else:
                self.LogMessage(irc, "E", "logfile created")
        self.logfile.write("%s %d %s\n" % (msgtype, time(), pformat(message)))
        self.logfile.flush()  # for now, instant flushing only.

    def add(self, irc, msg, args, channel, words):
        """[<channel>] <album>, <title>

        Add a song to the queue. To activate the first
        song in the queue, call 'next'. To show the first
        song in the queue, call 'shownext'"""

        if not self.Checkpriv(irc, msg, channel): return

        words = words.split(",", 1)
        if len(words) != 2:
            irc.error("USAGE EXAMPLE: add Accept, Lady Lou")
            return
        [album, title] = words

        album = album.strip()
        title = title.strip()

        self.LogMessage(irc, "A", {'album': album, 'title': title})

        self.pl.append((album, title))
        self.saved = False
        irc.replySuccess()
    add = wrap(add, ['channel', 'text'])

    def nextshow(self, irc, msg, args, channel, topic):
        """[<channel>] <TopicOfTheNextShow>

        Define the topic of the next show. This will be announced
        two days before the upcoming show."""

        if not self.Checkpriv(irc, msg, channel): return
        if topic == '': irc.reply("Topic of the next show is: %s" % self.nextSendung)
        else:
            self.nextSendung = topic
            self.saved = False
            irc.reply("Topic set. Will be announced two days before the show.")
    nextshow = wrap(nextshow, ['channel', additional('text', '')])

    def simannounce(self, irc, msg, args, channel, curTime):
        """[<channel>] <time in secs since jan1st1970

        Debug function"""

        if not self.Checkpriv(irc, msg, channel): return

        self.DoAnnouncements(curTime)
    simannounce = wrap(simannounce, ['channel', 'nonNegativeInt'])

    def show(self, irc, msg, args, channel):
        """[<channel>]

            Show complete playlist"""

        if not self.Checkpriv(irc, msg, channel): return

        response = ['There are %d pieces in the playlist.' % len(self.pl)]
        cnt = 0
        for item in self.pl:
            response.append("%d) %s [%s]" % (cnt, item[1], item[0]))
            cnt = cnt + 1
        irc.reply(" | ".join(response))
    show = wrap(show, ['channel'])

    def remove(self, irc, msg, args, channel, entry):
        """[<channel>] ID

            Delete an entry"""
        if not self.Checkpriv(irc, msg, channel): return
        try:
            album, title = self.pl[int(entry)]
            del self.pl[int(entry)]
            self.LogMessage(irc, "D", {'album': album, 'title': title})
            irc.replySuccess()
            self.saved = False
        except Exception, e: irc.error(pformat(e))
    remove = wrap(remove, ['channel', 'text'])


    def next(self, irc, msg, args, channel):
        """[<channel>]

            Show song that gets activated by calling 'next'"""

        if not self.Checkpriv(irc, msg, channel): return
        if not len(self.pl):
            irc.reply("The playlist is empty")
        else:
            irc.reply("A call to activate would activate %s from %s" % (self.pl[0][1], self.pl[0][0]))
    next = wrap(next, ['channel'])

    def activate(self, irc, msg, args, channel, trackID):
        """[<channel>] [<trackID>]

            Activate song in the playlist. If trackID is not
            specified, the next track in the queue is used."""

        if not self.Checkpriv(irc, msg, channel): return
        if not len(self.pl):
            irc.error("The playlist is empty! Add a song by calling 'add \"album\" \"title\"")
            return

        if not self.sendChannel in irc.state.channels:
            irc.error("I am not joined in %s" % self.sendChannel)
            return

        try:
            album, title = self.pl.pop(trackID)
            self.saved = False
        except:
            irc.error("Invalid ID. Issue !show to see all valid IDs")
            return

        self.playing[channel] = {"album": album, "title": title}
        self.LogMessage(irc, "M", (channel, self.playing))

        #mts = self.sendMsg % (title, album)
        #pmsg = privmsg(self.sendChannel, mts)
        #irc.queueMsg(pmsg)

        anChannel = self.registryValue('announcementChannel', channel)
        if (len(anChannel) < 1) or (anChannel[0] != '#'):
            for line in """No announcement channel is defined for this control channel.
This usually means that you're in the wrong channel or forgot to
configure an announcement channel.
Hint: for #c-radar, the control channel is #c-radar-intern ;)""".split("\n"): irc.error(line)
            return
        if not anChannel in irc.state.channels:
            irc.error("I'm not on channel %s, to which the announcements should go" % anChannel)
            return
        if irc.nick not in irc.state.channels[anChannel].ops:
            irc.error("I need to be opped in %s" % anChannel)
            return
        mts = irc.state.channels[anChannel].topic
        pos = mts.find(self.sendMsg)
        if pos != -1: mts = mts[0:pos]
        mts = mts + self.sendMsg + (self.titleFormat % self.playing)

        tmsg = topic(anChannel, mts)
        irc.queueMsg(tmsg)

        irc.replySuccess()
    activate = wrap(activate, ['channel', additional('nonNegativeInt', 0)])

    def finished(self, irc, msg, args, channel):
        """[<channel>]

            Mark a song as finished. Should be called as soon as a song if over."""

        if not self.Checkpriv(irc, msg, channel): return
        if self.playing == None:
            irc.error("No song is playing right now")
            return
        self.LogMessage(irc, "S", self.playing)
        self.playing = None

        mts = irc.state.channels[self.sendChannel].topic
        pos = mts.find(self.sendMsg)
        if pos != -1:
            mts = mts[0:pos]
            tmsg = topic(self.sendChannel, mts)
            irc.queueMsg(tmsg)

        irc.replySuccess()
    finished = wrap(finished, ['channel'])

    def clear(self, irc, msg, args, channel):
        """[<channel>]

            Clear playlist"""
        if not self.Checkpriv(irc, msg, channel): return
        l = len(self.pl)
        while len(self.pl): self.pl.pop()
        parms = [l]
        if l == 1: parms.append("y")
        else: parms.append("ies")
        parms = tuple(parms)
        self.playing = None
        self.LogMessage(irc, "E", "logfile closed")
        self.saved = False
        irc.reply("%d entr%s cleared. New logfile opened." % parms)
        if self.logfile != None:
            try:
                self.logfile.close()
            except: pass
            self.logfile = None
    clear = wrap(clear, ['channel'])

    def nowplaying(self, irc, msg, args, channel):
        """[<channel>]

            Show piece currently playing"""

        if self.playing == None:
            irc.reply("Currently, no song is playing")
        else:
            irc.reply("Now playing %(title)s from %(album)s" % self.playing)
    nowplaying = wrap(nowplaying, ['channel'])

    def help(self, irc, msg, args, text):
        """NO ARGS

            For help, see http://www.hcesperer.org/supybot/playlist/commands.html"""
        irc.reply("See http://www.hcesperer.org/supybot/playlist/commands.html")
        #irc.reply(irc.state.channels[channel].topic)
    help = wrap(help, [additional('text')])

Class = Playlist


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
