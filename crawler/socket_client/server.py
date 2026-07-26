import asyncio
import json
import logging
import os
import socket
import struct
import sys
import time
from dataclasses import dataclass
from enum import IntEnum

from conf.conf import conf
from jobhandler.jobhandler import jobhandler
from models.models import Job

logger = logging.getLogger(__name__)

# ============================================================
# CONFIG
# ============================================================

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

        payload = conf.broker_secret.encode()

        connect_msg = Message(
            length=len(payload) + 1,
            msg_type=MessageType.CONNECT,
            payload=payload,
        )

        self.send(connect_msg)
        print("Connected to broker.")

        await asyncio.gather(
            self.reader(),
            self.writer(),
            self.pull_loop(),
            self.heartbeat_loop(),
        )

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
        logger.info(f"Processing job {job.id}")
        try:
            await asyncio.to_thread(jobhandler, job.data)
        except Exception as e:
            logger.error(f"Error processing job {job.id}: {e}", exc_info=True)

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
        # if msg.msg_type == MessageType.TACK:
        #     sys.exit(0)

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
