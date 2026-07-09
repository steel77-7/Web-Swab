# import asyncio
# import os
# import socket
# import struct
# import sys
# from enum import Enum

# from dotenv import load_dotenv
# from main import jobhandler

# load_dotenv()


# class MessageType(Enum):
#     CONNECT = 1
#     HEARTBEAT = 2
#     TACK = 3
#     PULL = 4
#     INVALID = 5


# class Message:
#     length: int
#     msg_type: MessageType
#     payload: bytes


# class BrokerClient:
#     def __init__(self):
#         brokerip = os.getenv("BROKER_URL")
#         port = os.getenv("PORT")
#         try:
#             self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         except socket.error as err:
#             print("Error while creating the socket", err)
#             sys.exit()

#         try:
#             if brokerip is None or port is None:
#                 return
#             self.brokerip = socket.gethostbyname(brokerip)
#             self.port = port
#         except socket.gaierror as err:
#             print("Error while setting up the host ip : ", err)
#             sys.exit()
#         self.queue = asyncio.Queue()
#         self.is_job_present = False

#     # setting up the connection
#     def connect(self):
#         self.s.connect((self.brokerip, self.port))
#         print("Connection established")
#         # further auth logic
#         payload = "secret"  # this will be api key
#         payload = payload.encode("UTF-8")
#         length = len(payload) + 1
#         type = MessageType.CONNECT
#         header = struct.pack(">IB", length, type)
#         try:
#             self.s.send(header)
#             # now to send the data
#             self.s.sendall(payload)
#         except Exception as err:
#             print("Error occuredf while authenticating", err)
#             # return
#             sys.exit()
#         # then run the read loop
#         asyncio.create_task(self.readloop())

#     async def readloop(self):
#         while True:
#             try:
#                 # a parsing function
#                 self.s.recv(4)  # this is the length in the big endian
#             except Exception as err:
#                 print("Error while reading the data", err)
#                 sys.exit()

#     async def heartbeat(self):
#         tbs = Message()
#         tbs.payload = b""
#         tbs.length = len(tbs.payload) + 1
#         tbs.msg_type = MessageType.HEARTBEAT
#         await self.queue.put(tbs)

#     async def messageHandler(self, data):
#         match data.msg_type:
#             case MessageType.HEARTBEAT:
#                 if data.payload == "0":
#                     print("Some error i did not expect occured in hearbeat ")
#                     return
#             case MessageType.TACK:
#                 if data.payload == "0":
#                     print("Some error i did not expect occured in tack")
#                     return
#             case MessageType.PULL:
#                 # here will be a handler func that will have all the jobs
#                 # when the job is finished only then ask for another job
#                 self.is_job_present = True
#                 jobhandler(data.payload.decode("UTF-8"))
#                 self.is_job_present = False

#     async def pull_job(self):
#         while True:
#             if self.is_job_present:
#                 continue
#             # create a job request and ask for a job
#             tbs = Message()
#             tbs.payload = b""
#             tbs.length = len(tbs.payload) + 1
#             tbs.msg_type = MessageType.PULL
#             await self.queue.put(tbs)

#     async def writer(self):
#         while True:
#             tbs = self.queue.get()
#             try:
#                 self.send(tbs)
#             except Exception as err:
#                 print("Error it the writer func of the socket handler", err)
#                 return

#     def send(self, tbs):
#         headers = struct.pack(">IB", tbs.length, tbs.msg_type)
#         try:
#             self.s.sendall(headers + tbs.paylaod)
#         except Exception as err:
#             return err
import asyncio
import json
import os
import socket
import struct
import time
from dataclasses import dataclass
from enum import IntEnum

from conf.conf import conf
from jobhandler.jobhandler import jobhandler
from models.models import Job

# ============================================================
# CONFIG
# ============================================================

BROKER_HOST = os.getenv("BROKER_URL")
BROKER_PORT = os.getenv("TCP_SERVER_PORT")
SECRET = os.getenv("SECRET")

HEARTBEAT_INTERVAL = 0.1  # 100ms


# ============================================================
# PROTOCOL
# ============================================================


class MessageType(IntEnum):
    CONNECT = 0
    HEARTBEAT = 1
    TACK = 2
    PULL = 3
    INVALID = 4


@dataclass
class Message:
    length: int
    msg_type: MessageType
    payload: bytes


@dataclass
class JobInfo:
    id: str
    data: Job


# ============================================================
# CLIENT
# ============================================================


class BrokerClient:
    def __init__(self):

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)

        self.queue = asyncio.Queue()

        self.pull_event = asyncio.Event()
        self.pull_event.set()

        self.running = True

    # --------------------------------------------------------

    async def connect(self):

        self.sock.connect((conf.broker_url, conf.broker_tcp_port))
        self.brokeruri = conf.broker_url + str(conf.broker_http_port)
        print("Connected to broker.")

        payload = conf.broker_secret.encode()

        connect = Message(
            length=len(payload) + 1,
            msg_type=MessageType.CONNECT,
            payload=payload,
        )

        self.send(connect)

        asyncio.create_task(self.reader())
        asyncio.create_task(self.writer())
        asyncio.create_task(self.pull_loop())
        asyncio.create_task(self.heartbeat_loop())

    # --------------------------------------------------------

    def recv_exact(self, size: int):

        data = b""

        while len(data) < size:
            chunk = self.sock.recv(size - len(data))

            if not chunk:
                raise ConnectionError("Broker disconnected.")

            data += chunk

        return data

    # --------------------------------------------------------

    async def reader(self):

        try:
            while self.running:
                header = await asyncio.to_thread(
                    self.recv_exact,
                    5,
                )

                length = struct.unpack(">I", header[:4])[0]
                msg_type = MessageType(header[4])

                payload = b""

                if length > 1:
                    payload = await asyncio.to_thread(
                        self.recv_exact,
                        length - 1,
                    )

                msg = Message(
                    length=length,
                    msg_type=msg_type,
                    payload=payload,
                )

                await self.message_handler(msg)

        except Exception as e:
            print("Reader stopped:", e)

            await self.close()

    # --------------------------------------------------------

    async def writer(self):

        try:
            while self.running:
                msg = await self.queue.get()

                await asyncio.to_thread(
                    self.send,
                    msg,
                )

        except Exception as e:
            print("Writer stopped:", e)

            await self.close()

    # --------------------------------------------------------

    async def heartbeat_loop(self):

        while self.running:
            payload = str(int(time.time()) + 10).encode()

            await self.queue.put(
                Message(
                    length=len(payload) + 1,
                    msg_type=MessageType.HEARTBEAT,
                    payload=payload,
                )
            )

            await asyncio.sleep(HEARTBEAT_INTERVAL)

    # --------------------------------------------------------

    async def pull_loop(self):

        while self.running:
            await self.pull_event.wait()

            self.pull_event.clear()

            await self.queue.put(
                Message(
                    length=1,
                    msg_type=MessageType.PULL,
                    payload=b"",
                )
            )

    # --------------------------------------------------------

    async def message_handler(self, msg: Message):

        if msg.msg_type == MessageType.HEARTBEAT:
            if msg.payload == b"0":
                print("Heartbeat rejected by broker.")
                await self.close()

        elif msg.msg_type == MessageType.TACK:
            if msg.payload == b"0":
                print("Broker rejected ACK.")
                await self.close()

        elif msg.msg_type == MessageType.PULL:
            if not msg.payload or msg.payload == b"0":
                self.signal_pull()
                return

            try:
                jobs = json.loads(msg.payload.decode())

            except Exception as e:
                print("Invalid job payload:", e)
                self.signal_pull()
                return

            for job in jobs:
                job = JobInfo(
                    id=job["id"],
                    data=job["data"],
                )

                await self.process_job(job)

            self.signal_pull()

    # --------------------------------------------------------

    async def process_job(self, job: JobInfo):
        """
        =======================================================
        PLACE YOUR JOB HANDLER HERE
        =======================================================

        Replace this with your own worker logic.

        Example:

            await jobhandler(job ,conf)

        or

            result = await jobhandler(job)

        =======================================================
        """
        print(f"Processing job {job.id}")
        jobhandler(job.data)

        # -----------------------------------
        # YOUR CODE HERE
        # -----------------------------------

        # await jobhandler(job)

        # -----------------------------------

        ack = Message(
            length=len(job.id.encode()) + 1,
            msg_type=MessageType.TACK,
            payload=job.id.encode(),
        )

        await self.queue.put(ack)

    # --------------------------------------------------------

    def signal_pull(self):

        self.pull_event.set()

    # --------------------------------------------------------

    def send(self, msg: Message):

        header = struct.pack(
            ">IB",
            msg.length,
            int(msg.msg_type),
        )

        self.sock.sendall(header + msg.payload)

    # --------------------------------------------------------

    async def close(self):

        if not self.running:
            return

        self.running = False

        self.pull_event.set()

        try:
            self.sock.close()
        except:
            pass

        print("Disconnected from broker.")


# ============================================================
# MAIN
# ============================================================


async def main():

    client = BrokerClient()

    await client.connect()

    while client.running:
        await asyncio.sleep(1)


if __name__ == "__main__":
    asyncio.run(main())
