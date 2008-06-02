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

import threading
import socket

from time import time, localtime, mktime, ctime, sleep
from pprint import pformat
import os
import sys
import weakref
import random
from sha import sha

MAX_TIMEOUT = 60


class EOFException(Exception): pass

def ParseParam(ptp):
    B64MARKER = '_B64_'
    if ptp.startswith(B64MARKER):
        try: return ptp[len(B64MARKER):].decode('base64')
        except: return ptp
    else: return ptp

class LineReader:
    buf = ''
    CANCELAT = 8192 # max line length
    def __init__(self, socket):
        self.s = socket
    def readline(self):
        while True:
            pos = self.buf.find("\n")
            if pos != -1:
                line, self.buf = self.buf[:pos], self.buf[pos + 1:]
                return line
            if len(self.buf) > self.CANCELAT:
                # cause a panic
                try: self.s.close()
                except: pass
                return ''
            frag = self.s.recv(8192)
            if frag == None: raise EOFException()
            if len(frag) == 0: raise EOFException()
            frag = frag.replace("\r", "")
            if len(frag) == 0:
                buf, self.buf = self.buf, ''
                return buf # EOF
            self.buf = self.buf + frag

class SockHandler(threading.Thread):
    AUTHPASSWORD = 'REGSsg!9#(@fooBPAssfuckingPhraseChangeThisSoon'
    def __init__(self, socket, address, irc, plugin, commandlock):
        threading.Thread.__init__(self)
        self.s = socket
        self.address = address
        self.irc = irc
        self.plugin = plugin
        self.commandlock = commandlock
        self.authinfo = None
        self.authed = False
        self.dostop = False
    def FCT_getauth(self, parms):
        if self.authinfo != None:
            self.s.sendall('201 auth already sent\n')
            return
        if len(parms) < 1:
            self.s.sendall('340 getauth NONCE\n')
            return
        nonce = parms[0]
        if len(nonce) < 8:
            self.s.sendall('341 nonce too short\n')
            return
        authcode = sha('%d' % random.randrange(1 << 31)).hexdigest()
        self.authinfo = (authcode, nonce)
        self.s.sendall('200 %s\n' % authcode)
    def FCT_auth(self, parms):
        if self.authinfo == None:
            self.s.sendall('503 getauth first\n')
            return
        if len(parms) < 1:
            self.s.sendall('340 auth CRESPONSE\n')
            return
        SHA_plaintext = '%s%s%s' % (self.authinfo[1], self.authinfo[0], self.AUTHPASSWORD)
        hcode = sha(SHA_plaintext).hexdigest()
        if hcode != parms[0]:
            self.s.sendall('109 invalid auth\n')
            return
        self.s.sendall('200 authenticated\n')
        self.authed = True
    def FCT_activate(self, parms):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        try: [album, title] = parms
        except:
            self.s.sendall('340 add ALBUM, TITLE\n')
            return
        self.plugin.playing = {"album": album, "title": title}
        self.plugin.DoActivate()
        self.s.sendall("200 track queued\n")
    def FCT_gettopic(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        self.s.sendall('200 %s\n' % self.irc.state.channels[self.plugin.sendChannel].topic)
    def FCT_getops(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        self.s.sendall('200 %s\n' % " ".join(self.irc.state.channels[self.plugin.sendChannel].ops))
    def FCT_getusers(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        self.s.sendall('200 %s\n' % " ".join(self.irc.state.channels[self.plugin.sendChannel].users))
    def FCT_finish(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        if self.plugin.playing == None:
            self.s.sendall('201 no track playing ATM\n')
            return
        self.plugin.DoFinish()
        self.s.sendall('200 track is finished\n')
    def FCT_ping(self, params):
        self.s.sendall('200 pong\n')
    def FCT_settopic(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        t_un = ''
        if len(params) < 1:
            tmsg = topic(self.plugin.sendChannel, ' ')
            t_un = 'un'
        else:
            mytopic = " | ".join(params)
            tmsg = topic(self.plugin.sendChannel, mytopic)
        self.plugin.irc.queueMsg(tmsg)
        self.s.sendall('200 topic %sset\n' % t_un)
    def FCT_show(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        pass
    def FCT_clear(self, params):
        if not self.authed:
            self.s.sendall('503 auth first\n')
            return
        pass
    def FCT_quit(self, parms):
        self.s.sendall('400 Auf Wiedersehen!\n')
        self.dostop = True
        try: self.s.close()
        except: pass
    def stop():
        self.dostop = True
        try: self.s.close()
        except: pass
    def run(self):
        s = self.s
        s.settimeout(MAX_TIMEOUT)
        lr = LineReader(s)
        functions = self.__class__.__dict__
        try:
            while not self.dostop:
                try: line = lr.readline()
                except socket.timeout:
                    self.dostop = True
                    try: self.s.sendall('100 timeout\n')
                    except: pass
                    try: self.s.close()
                    except: pass
                    break
                line = line.split(' ', 1)
                if len(line) < 1:
                    continue
                command = line[0]
                if len(line) > 1:
                    parms = line[1].split(',')
                    parms = [ParseParam(i) for i in parms]
                else: parms = []
                try: function = functions['FCT_%s' % command]
                except:
                    s.sendall('302 function does not exist\n')
                    continue
                try:
                    try:
                        self.commandlock.acquire_lock() # this lock is per playlist plugin instance
                        res = function.__call__(self, parms)
                    finally: self.commandlock.release_lock()
                except Exception, e:
                    s.sendall('303 function error: %s\n' % repr(type(e)))
                    continue
        except Exception, e:
            print "Error: exception occured: %s" % repr(e)
            try: s.sendall('100 terminating: %s\n' % repr(type(e)))
            except: pass
            try: s.close()
            except: pass
            print 'done.'

class ConnectionLimitExceeded(threading.Thread):
    def __init__(self, socket, address):
        threading.Thread.__init__(self)
        self.s = socket
        self.a = address
    def run(self):
        self.s.settimeout(MAX_TIMEOUT)
        try: self.s.sendall('301 Connection limit from this IP exceeded\n')
        except Exception, e: print 'ConnectionLimitExceeded: %s' % repr(e)
        try: self.s.close()
        except Exception, e: print 'ConnectionLimitExceeded: %s' % repr(e)

class SockListener(threading.Thread):
    def __init__(self, address, irc, plugin):
        threading.Thread.__init__(self)
        self.address = address
        self.irc = irc
        self.plugin = plugin
        self.dostop = False
        self.commandlock = threading.Lock()
        self.listeners = weakref.WeakValueDictionary()
    def __del__(self):
        print 'Connection handler for %s died.\n' % (self.address)
        for handler in self.listeners:
            print "SockListener: Stopping %s" % repr(handler)
            self.listeners[handler].stop()
    def stop(self):
        self.dostop = True
        try: self.s.close()
        except: pass
    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s = s
        while not self.dostop:
            try: s.bind(self.address)
            except:
                print "SockListener: Error: cannot bind to %s" % repr(self.address)
                sleep(60)
                continue
            s.listen(2) # backlog: 2 entries
            print "Listening on %s" % repr(self.address)
            while not self.dostop:
                try: cs, a = s.accept()
                except: continue
                if a[0] in self.listeners:
                    print 'SockListener: %s is in self.listeners' % repr(a[0])
                    ConnectionLimitExceeded(cs, a).start()
                    continue
                print "SockListener: Accepted connection from %s" % repr(a)
                handler = SockHandler(cs, a, self.irc, self.plugin, self.commandlock)
                handler.setDaemon(True)
                self.listeners[a[0]] = handler
                handler.start()
                handler = None # so that garbage collection works properly -- we depend on that!
        try:
            s.close()
            print 'SockListener: Main socket successfully closed'
        except: pass
        s = None


class Playlist(callbacks.Plugin):
    """HC's  Radio playlist plugin"""

    # manually saved/loaded stuff
    sendChannel = "#c-radar"
    sendMsg = " | now playing: "
    titleFormat = "%(title)s from %(album)s"
    nextSendung = "Details for the next show can be found at http://www.c-radar.de/"
    miscStuff = ["http://www.c-radar.de", "fm 103,4 MHz"]
    msgSeparator = " | "
    feedbackMsg = "The show is over; send your feedback to studio@c-radar.de"
    pl = []

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
        self.sl = SockListener(('0.0.0.0', 1723), irc, self)
        self.sl.setDaemon(True)
        self.sl.start()
        world.flushers.append(self.flusher)
        try: self.LoadSettings()
        except Exception, e:
            sys.stderr.write("Couldn't load settings; using defaults. (%s)" % e)
            self.saved = False

    def die(self):
        try: self.sl.stop()
        except Exception, e: print 'Stopping SockListener: %s' % e
        world.flushers = [x for x in world.flushers if x is not self.flusher]

    def Checkpriv(self, irc, msg, channel):
        isOK = True
        if not self.CheckRightChannel(irc, channel):
            isOK = False
        if channel not in irc.state.channels:
            irc.error("No.")
            return False
        if msg.nick not in irc.state.channels[channel].ops:
            if isOK:
                irc.error("You can't do that thing, when you don't have that swing. (You're not channel operator)")
            else:
                irc.error("In addition to that, you don't have that swing, that you need to do that thing (You're not channel operator)")
            return False
        return True

    def DataDir(self):
        dataDir = conf.supybot.directories.data.dirize(self.name())
        if not os.path.exists(dataDir): os.makedirs(dataDir)
        return dataDir

    def CheckRightChannel(self, irc, channel):
        if channel != '#c-radar-intern':
            for line in """This command may only be issued in #c-radar-intern.
If you want to issue this command in a private query with the bot,
you may do so, as long as:
  a) you specify #c-radar-intern as first parameter to the command
  b) you are in the channel #c-radar-intern and
  c) you are chanop of #c-radar-intern.
If you've got additional questions, mail hc@hcesperer.org""".split("\n"): irc.error(line)
            return False
        return True

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

        self.playing = {"album": album, "title": title}
        self.DoActivate()
        irc.replySuccess()
    activate = wrap(activate, ['channel', additional('nonNegativeInt', 0)])

    def DoActivate(self):
        irc = self.irc
        self.LogMessage(irc, "M", self.playing)

        #mts = self.sendMsg % (title, album)
        #pmsg = privmsg(self.sendChannel, mts)
        #irc.queueMsg(pmsg)

        mts = irc.state.channels[self.sendChannel].topic
        pos = mts.find(self.sendMsg)
        if pos != -1: mts = mts[0:pos]
        mts = mts + self.sendMsg + (self.titleFormat % self.playing)

        tmsg = topic(self.sendChannel, mts)
        irc.queueMsg(tmsg)

    def finished(self, irc, msg, args, channel):
        """[<channel>]

            Mark a song as finished. Should be called as soon as a song if over."""

        if not self.Checkpriv(irc, msg, channel): return
        if self.playing == None:
            irc.error("No song is playing right now")
            return
        self.DoFinish()
        irc.replySuccess()
    finished = wrap(finished, ['channel'])

    def DoFinish(self):
        self.playing = None
        self.LogMessage(self.irc, "S", self.playing)
        mts = self.irc.state.channels[self.sendChannel].topic
        pos = mts.find(self.sendMsg)
        if pos != -1:
            mts = mts[0:pos]
            tmsg = topic(self.sendChannel, mts)
            self.irc.queueMsg(tmsg)

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

    def version(self, irc, msg, args, text):
        """NO ARGS

            Version is $Id$"""
        irc.reply("Version is $Id$")
        #irc.reply(irc.state.channels[channel].topic)
    version = wrap(version, [additional('text')])



Class = Playlist


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
