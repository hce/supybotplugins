import threading
import socket
from time import time, sleep
import random
from sha import sha

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

class WunderlichException(Exception): pass
class KWClient(threading.Thread):
    PINGINTERVAL = 30
    def __init__(self, addr, password):
        threading.Thread.__init__(self)
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.s.connect(addr)
        self.s.settimeout(self.PINGINTERVAL * 3)
        self.r = LineReader(self.s)
        self.lock = threading.Lock()
        self.dostop = False
        self.lastcmd = time()
        self.DoAuth(password)
    def DoAuth(self, password):
        rr = random.randrange(0, 1<<31)
        curtime = int(time())
        res, authcode = self.sendcmd('getauth %d%d\n' % (rr, curtime))
        if res != 200: raise WunderlichException('Error while requesting authcode')
        SHA_plaintext = '%d%d%s%s' % (rr, curtime, authcode, password)
        AUTH_MSG = sha(SHA_plaintext).hexdigest()
        res, msg = self.sendcmd('auth %s\n' % (AUTH_MSG))
        if res != 200: raise WunderlichException('Auth failed: %s' % msg)
        self.setDaemon(True)
        self.start()
    def send(self, string):
        self.lock.acquire_lock()
        try:
            self.s.sendall(string)
            lastcmd = time()
            return self.r.readline()
        finally: self.lock.release_lock()
    def stop(self):
            self.dostop = True
            try: self.s.close()
            except: pass
    def run(self):
        while not self.dostop:
            sleep(self.PINGINTERVAL / 2)
            if (time() - self.lastcmd) > self.PINGINTERVAL :
                code = -1
                try:
                    code, msg = self.sendcmd('ping\n')
                except: pass
                if code != 200:
                    print 'Error: ping failed: %s' % msg
    def sendcmd(self, cmd):
        res = self.send(cmd)
        if res == None:
            return -1, ''
        [code, msg] = res.split(' ', 1)
        return int(code), msg
    def activate(self, album, title):
        code, msg = self.sendcmd('activate _B64_%s,_B64_%s\n' % (album.encode('base64').replace("\n", ""), title.encode('base64').replace("\n", "")))
        if code == 200: return True
        return False
    def finish(self):
        code, msg = self.sendcmd('finish\n')
        if code == 200: return True
        return False
    def settopic(self, topic):
        code, msg = self.sendcmd('settopic _B64_%s\n' % topic.encode('base64').replace("\n", ""))
        if code == 200: return True
        return False
    def gettopic(self):
        code, msg = self.sendcmd('gettopic\n')
        if code != 200: raise WunderlichException("Could not get topic")
        return msg
    def getops(self):
        code, msg = self.sendcmd('getops\n')
        if code != 200: raise WunderlichException("Unable to get opped users")
        return msg.split(" ")
    def getusers(self):
        code, msg = self.sendcmd('getusers\n')
        if code != 200: raise WunderlichException("Unable to get opped users")
        return msg.split(" ")

