import asyncio
import socket
import struct
import sys
from enum import Enum


class MessageType(Enum):
    CONNECT = 1
    HEARTBEAT = 2
    TACK = 3
    PULL = 4
    INVALID = 5


class Message:
    length: int
    msg_type: MessageType
    payload: bytes


class BrokerClient:
    def __init__(self, brokerip, port):
        try:
            self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        except socket.error as err:
            print("Error while creating the socket", err)
            sys.exit()
        try:
            self.brokerip = socket.gethostbyname(brokerip)
            self.port = port
        except socket.gaierror as err:
            print("Error while setting up the host ip : ", err)
            sys.exit()
        self.queue = asyncio.Queue()
        self.is_job_present = False

    # setting up the connection
    def connect(self):
        self.s.connect((self.brokerip, self.port))
        print("Connection established")
        # further auth logic
        payload = "apsoidfhgoasdfhgosjadfhgasdfh"  # this will be api key
        payload = payload.encode("UTF-8")
        length = len(payload) + 1
        type = MessageType.CONNECT
        header = struct.pack(">IB", length, type)
        try:
            self.s.send(header)
            # now to send the data
            self.s.sendall(payload)
        except Exception as err:
            print("Error occuredf while authenticating")
            # return
            sys.exit()
        # then run the read loop
        asyncio.create_task(self.readloop())

    async def readloop(self):
        while True:
            try:
                # a parsing function
                self.s.recv(4)  # this is the length in the big endian
            except Exception as err:
                print("Error while reading the data", err)
                sys.exit()

    async def heartbeat(self):
        tbs = Message()
        tbs.payload = b""
        tbs.length = len(tbs.payload) + 1
        tbs.msg_type = MessageType.HEARTBEAT
        await self.queue.put(tbs)

    def messageHandler(self, data):
        match data.msg_type:
            case MessageType.HEARTBEAT:
                if data.payload == "0":
                    print("Some error i did not expect occured in hearbeat ")
                    return
            case MessageType.TACK:
                if data.payload == "0":
                    print("Some error i did not expect occured in tack")
                    return
            case MessageType.PULL:
                # here will be a handler func that will have all the jobs
                # when the job is finished only then ask for another job
                self.is_job_present = True

    async def pull_job(self):
        while True:
            if self.is_job_present:
                continue
            # create a job request and ask for a job
            tbs = Message()
            tbs.payload = b""
            tbs.length = len(tbs.payload) + 1
            tbs.msg_type = MessageType.PULL
            await self.queue.put(tbs)

    async def writer(self):
        while True:
            tbs = self.queue.get()
            try:
                self.send(tbs)
            except Exception as err:
                print("Error it the writer func of the socket handler", err)
                return

    def send(self, tbs):
        headers = struct.pack(">IB", tbs.length, tbs.msg_type)
        try:
            self.s.sendall(headers + tbs.paylaod)
        except Exception as err:
            return err
