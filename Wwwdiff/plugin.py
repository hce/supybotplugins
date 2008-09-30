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
from supybot.ircmsgs import privmsg, topic, IrcMsg

import time
import urllib
import difflib
import threading
import extracthtml

notwant = [
        "Diese Seite wurde bisher",
        "Diese Seite wurde zuletzt",
        "$Id "
    ]

def filter(s):
    eh = extracthtml.ExtractHTML()
    eh.feed(s)
    eh.close()
    return " ".join(eh.get_stuff())

def unwanted(s):
    for nw in notwant:
        if s.find(nw) != -1: return True
    return False

class WWWCrawler(threading.Thread):
    def __init__(self, plugin):
        threading.Thread.__init__(self)
        self.plugin = plugin
        self.texts = {}
        self.stopped = False
        self.urls = [
                ("https://usualsuspect:freundschaft@orga.cccv.de/congress/2008/wiki/index.php/Hacking_contest", "(ctfhc) Hacking Contest", "#25c3-ctf-orga"),
                ("https://usualsuspect:freundschaft@orga.cccv.de/congress/2008/wiki/index.php?title=Diskussion:Hacking_contest", "(ctfhc) CTF Discussion", "#25c3-ctf-orga"),
                ("http://ctf.sec.informatik.tu-darmstadt.de/daopen08/", "da-op3n", "#da-op3n"),
                ("http://blog.fefe.de", "fefe", "#fefe"),
                ("http://www.fefe.de", "fefe", "#fefe")
            ]
    def stop(self):
        self.stopped = True
    def run(self):
        while not self.stopped:
            time.sleep(10)
            for url, desc, chan in self.urls:
                try:
                    f = urllib.urlopen(url)
                    s = f.read()
                    f.close()
                    s = filter(s)
                except Exception, e:
                    msg = privmsg("hc", "Wwwdiff: error(1): %s" % e)
                    self.plugin.irc.queueMsg(msg)
                    continue
                try:
                    old = self.texts[url]
                    self.texts[url] = s
                except:
                    self.texts[url] = s
                    continue
                try:
                    diffs = difflib.ndiff(old.split("\n"), s.split("\n"))
                    for diff in diffs:
                        if unwanted(diff): continue
                        if diff[0] == '+':
                            msg = privmsg(chan, "C [%s] %s" % (desc, diff))
                            self.plugin.irc.queueMsg(msg)
                except Exception, e:
                    msg = privmsg("hc", "Wwwdiff: error(2): %s" % e)
                    self.plugin.irc.queueMsg(msg)
                    continue
            time.sleep(3600 * 3)


class Wwwdiff(callbacks.Plugin):
    """HC's webdiff plugin. (C) 2008, HC Esperer ;-)"""
    threaded = True
    def __init__(self, irc):
        self.__parent = super(Wwwdiff, self)
        self.__parent.__init__(irc)
        self.irc = irc
        self.crawler = WWWCrawler(self)
        self.crawler.setDaemon(True)
        self.crawler.start()
    def __del__(self):
        self.crawler.stop()



Class = Wwwdiff


# vim:set shiftwidth=4 tabstop=4 expandtab textwidth=79:
