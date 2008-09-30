import urllib
import htmllib

def ListTuplesToDict(tuples):
    d = {}
    for k, v in tuples:
        d[k] = v
    return d
class ExtractHTML(htmllib.HTMLParser):
    def __init__(self):
        htmllib.HTMLParser.__init__(self, None)
        self.read = 0
        self.foo = []
        self.stuff = []
        self.tags = [
                'a', 'p', 'li'
            ]
    def handle_starttag(self, tag, attrs, foo):
        attrs = ListTuplesToDict(foo)
        if tag in self.tags:
            self.read = 1
        if tag.lower() == 'a':
            if 'href' in attrs: self.stuff.append("(%s)" % attrs['href'])
    def handle_endtag(self, tag, foo):
        if tag in self.tags:
            self.read = 0
            self.stuff.append("\n")
    def handle_data(self, text):
        if self.read:
            self.stuff.append(text)
    def get_stuff(self): return self.stuff


if __name__ == '__main__':
    eh = ExtractHTML()
    eh.feed(urllib.urlopen("http://www.google.de/").read())
    eh.close()
    
    for line in eh.get_stuff():
        print line
