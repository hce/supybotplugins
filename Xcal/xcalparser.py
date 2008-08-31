# xcal small parser
# (C) 2008, Hans-Christian Esperer
# Released under the 3-clause Berkeley Software
# Distribution license :-P

import xml.dom.minidom
import time
from httplib import HTTPConnection

class XCalException(Exception): pass


def getText(nodelist):
    rc = ""
    for node in nodelist:
        if node.nodeType == node.TEXT_NODE:
            rc = rc + node.data
    return rc



class XCalEvent:
    def __init__(self, dom):
        self.items = {}
        for n in dom.childNodes:
            if n.nodeType == n.ELEMENT_NODE:
                try: l = self.items[n.nodeName]
                except:
                    l = []
                    self.items[n.nodeName] = l
                l.append(getText(n.childNodes))
    def get(self, key, default=None, firstOnly=True):
        try: l = self.items[key]
        except:
            if firstOnly: return default
            else: return [default]
        if firstOnly:
            if len(l): return l[0]
            else: return default
        else: return l
    def dict(self):
        d = {}
        for k in self.items:
            v = self.items[k]
            if len(v) > 2:
	    	vtmp = ', '.join(v[:-1])
		v = " und ".join([vtmp, v[-1]])
            else: v = v[0]
            d[k] = v
        try: d['begintime'] = time.strftime('%H:%M', time.localtime(self.getTime('dtstart')))
        except: d['begintime'] = 'unknown'
        return d
    def getTime(self, key):
        rd = self.items[key][0]
        datetime = rd.split('T')
        return time.mktime(
                time.strptime(''.join(datetime), '%Y%m%d%H%M%S')
            )
    def __str__(self): return self.__unicode__()
    def __unicode__(self): return self.get('summary')

class XCal:
    def __init__(self, url=None, string=None):
        if (url == None) and (string == None):
            raise XCalException("url or string must be spec'ed")
        if (url != None) and (string != None):
            raise XCalException("Only url or string may be spec'ed")
        if url:
            host, path = url
            conn = HTTPConnection(host, 80)
            conn.putrequest("GET", path)
            conn.putheader("User-Agent", "HC's xcalparser $Id$ +http://www.hcesperer.org/xcalparser/")
            conn.endheaders()
            response = conn.getresponse()
            string = response.read()
        self.dom = xml.dom.minidom.parseString(string)
        self.DoParse(self.dom)
    def DoParse(self, dom):
        cal = dom.getElementsByTagName('iCalendar')[0]
        vcal = dom.getElementsByTagName('vcalendar')[0]
        events = dom.getElementsByTagName('vevent')
        self.events = []
        for event in events:
            xce = XCalEvent(event)
            starttime = xce.getTime('dtstart')
            self.events.append((starttime, xce))
        self.events.sort()
    def GetPostTimeEvents(self, time):
        return [e for e in self.events if e[0] > time]

        


if __name__ == '__main__':
    xcal = XCal(("mrmcd110b.metarheinmain.de", '/fahrplan/schedule.en.xcs'))
    for event in xcal.GetPostTimeEvents(0):
        print event[0], event[1].get('summary').encode('ansi')
