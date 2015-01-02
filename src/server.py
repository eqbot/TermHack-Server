'''
Created on Nov 25, 2014

@author: Trent
'''
from twisted.internet import reactor, defer
from twisted.internet.protocol import Factory
from twisted.protocols.basic import LineReceiver
import MySQLdb
import hashlib
import pickle
import random
from __builtin__ import None

def sleep(secs):
    d = defer.Deferred()
    reactor.callLater(secs, d.callback, None)
    return d

class PlayerData(object):
    def __init__(self):
        self.MOTD = None
        self.address = None
        self.files = None
        self.hardware = None
        self.bankaccounts = {'DeBank':200}
    def createPickle(self):
        return pickle.dumps(self)

class Server(object):
    def __init__(self,address):
        self.MOTD = None
        self.files = None
        self.hardware = None
        self.address = None
        self.type = "Basic"

class StoreServer(Server):
    def __init__(self,address,storetype):
        super(StoreServer,self).__init__(address)
        self.storetype = storetype
        self.items = []


class Hacker(LineReceiver):
    def __init__(self):
        self.uname = None
        self.login = False
        self.data = None
        self.state = "USERNAME"
        self.gamestate = None
        self.connected = None
    def connectionMade(self):
        self.transport.write('\x1B[7l')
        self.sendLine("What is your username? Alternatively, type 'register' to create a new account.")
    def connectionLost(self):
        #Pack up the user data.
        c = self.factory.db.cursor()
        c.execute("""UPDATE users SET data = %s, SET address = %s""", (self.data.createPickle(),self.data.address))
        c.close()
    def lineReceived(self, line):
        if self.state == "USERNAME":
            self.handle_AUTH(line)
        elif self.state == "PASSWORD":
            self.handle_LOGIN(line)
        elif self.state == "REGUSERNAME":
            self.register_USERNAME(line)
        elif self.state == "REGPASSWORD":
            self.register_PASSWORD(line)
        elif self.state == "WAITTODC":
            self.transport.loseConnection()
        elif self.state == "PLAY":
            self.play(line)
        else:
            self.sendLine("INVALID STATE. Give the developer the error 'state = " + self.state + "'")
            self.sendLine("We will now wait for an input before disconnecting.")
            self.state = "WAITTODC"
    def handle_AUTH(self,uname):
        uname = uname.lower()
        if uname == "register":
            self.sendLine("What username would you like?")
            self.state = "REGUSERNAME"
            return
        c = self.factory.db.cursor()
        #MySQLdb requires that the parameters be a sequence. Hence, the one-value tuple.
        c.execute("""SELECT username FROM users WHERE username = %s""", (uname,))
        if not c.fetchone() == None:
            #valid user
            self.uname = uname
            self.sendLine("What is your password?")
            self.state = "PASSWORD"
            c.close()
            return
        else:
            self.sendLine("Username not found. Retry.")
            c.close()
            return
    def handle_LOGIN(self,passwd):
        c = self.factory.db.cursor()
        c.execute("""SELECT data FROM users WHERE username = %s""",(self.uname,))
        if not c.fetchone() == None:
            #There is a password stored here, as there should be.
            hashedpass = hashlib.md5(passwd).hexdigest()
            if hashedpass == c.fetchone()[0]:
                #login is good
                self.login = True
                self.state = "PLAYING"
                #load user data
                pickledData = c.fetchone()[0]
                self.data = pickle.loads(pickledData)
        else:
            #There is no password! Tell the user to contact me.
            self.sendLine("Your userdata is missing a password. Contact /u/awolfers or trentkenn8@gmail.com to fix this.")
        c.close()
        return
    def register_USERNAME(self,username):
        c = self.factory.db.cursor()
        username = username.lower()
        c.execute("""SELECT username FROM users WHERE username = %s""",(username,))
        if c.fetchone() == None or username == "register":
            self.uname = username
            self.sendLine("What password would you like?")
            self.state = "REGPASSWORD"
            c.close()
            return
        else:
            self.sendLine("Username already taken or is invalid. Input a different username.")
            c.close()
            return
    def register_PASSWORD(self,passwd):
        c = self.factory.db.cursor()
        hashedpass = hashlib.md5(passwd).hexdigest()
        pdata = PlayerData()
        pdata.hardware = {'cpu':('Pentium 60',0.06)}
        validaddress = False
        while validaddress == False:
            ip = str(random.randint(0,255)) + '.' + str(random.randint(0,255)) + '.' + str(random.randint(0,255)) + '.' + str(random.randint(0,255))
            c.execute("""SELECT address FROM users WHERE address = %s""",(ip,))
            if c.fetchone() == None:
                #This IP is free
                validaddress = True
                pdata.address = ip
        c.execute("""INSERT INTO users (username,password,address) VALUES (%s,%s,%s)""",(self.uname,hashedpass,pdata.address))
        self.state = "PLAY"
        self.login = True
        self.gamestate = "LAUNCH"
        self.data = pdata
        c.close()
        return
    def connectServer(self,ip):
        c = self.factory.db.cursor()
        c.execute("SELECT data FROM users WHERE address = %s", (ip,))
        if c.fetchone() == None:
            return False
        self.connected = pickle.loads(c.fetchone()[0])
            return True
    def play(self,line):
        if self.gamestate == "LAUNCH":
            #display some random text
            self.transport.send('\x1B[2J')
            self.gamestate = "TERMINAL"
        elif self.gamestate == "TERMINAL":
            cmd = line.lower()
            if cmd == "help":
                for item in self.factory.helps:
                    self.sendLine(item)
            elif cmd == "clear":
                self.transport.send('\x1B[2J')
            elif cmd == "tips":
                self.sendLine('Send me your dogecoins! DFb46fCAMAjfZbD9DLVfcT4UYT4m3WheVG')
            elif cmd == "dc":
                if self.connected == None:
                    self.sendLine('You are not currently connected to a server.')
                else:
                    self.sendLine('Disconnected.')
                    self.connected = None
            elif "telnet" in cmd:
                args = cmd.split(' ')
                if self.connectServer(args[1]):
                    self.sendLine('Connected to ' + self.connected.address + '.')
                    self.sendLine('')
                    if self.connected.MOTD == None:
                        self.sendLine('This server has no MOTD configured')
                    else:
                        self.sendLine('MOTD :')
                        self.sendLine(self.connected.MOTD)
                else:
                    self.sendLine('Connection failed.')
            self.transport.send('>')
class HackerFactory(Factory):
    def __init__(self):
        #Connect to database and give protocols a handle to use
        self.helps = ["clear - Clear the screen","dc - Disconnects from server","dl - Download a file from remote","help - Displays this list","ls - Displays files","run - Runs/Installs a file","telnet - Connects to server", "tips - Display information on how to tip the developer."]
        self.db = MySQLdb.connect(user="server",passwd="ebola",db="TermHack")
    def buildProtocol(self,addr):
        return Hacker()

reactor.listenTCP(8123, HackerFactory())
reactor.run()