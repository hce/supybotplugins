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
import supybot.conf as conf
from supybot.ircmsgs import privmsg

from time import time
from pprint import pformat
import os

class Playlist(callbacks.Plugin):
    """Chaosradio Darmstadt Playlist plugin"""

    sendChannel = "#c-radar"
    sendMsg = "Now playing: %s from %s"
    noMusic = "Current topic: %s"
    topicMsg = "Welcome to C-Radar | http://www.c-radar.de | %s"
    logfile = None
    playing = None

    def __init__(self, irc):
        self.__parent = super(Playlist, self)
        self.__parent.__init__(irc)
        self.pl = []

    def Checkpriv(self, irc, msg, channel):
        if msg.nick not in irc.state.channels[channel].ops:
            irc.error("You can't do that thing, when you don't have that swing. (%s)" % msg.nick)
            return False
        return True

    def NewLog(self, irc):
        logDir = conf.supybot.directories.log.dirize(self.name())
        if not os.path.exists(logDir):
            os.makedirs(logDir)
        try:
            self.logfile = open("%s/CLOG%d.txt" % (logDir, time()), 'w')
        except Exception, e:
            irc.error("Cannot open logfile: %s" % e)

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
        irc.replySuccess()
    add = wrap(add, ['channel', 'text'])

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
        except:
            irc.error("Invalid ID. Issue !show to see all valid IDs")
            return

        self.playing = {"album": album, "title": title}
        self.LogMessage(irc, "M", self.playing)

        mts = self.sendMsg % (title, album)
        pmsg = privmsg(self.sendChannel, mts)
        irc.queueMsg(pmsg)

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

    def help(self, irc, msg, args, channel):
        """[<channel>]

            For help, see http://78.47.168.174/playlist.txt"""
        irc.reply("See http://78.47.168.174/playlist.txt")
    help = wrap(help, ['channel'])

Class = Playlist


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
