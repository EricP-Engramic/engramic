# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

import logging

import zmq
import zmq.asyncio
from engramic.infrastructure.system.service import Service


class BaseMessageService(Service):
    def __init__(self, event_loop):
        super().__init__(event_loop)

    def init_async(self):
        self.pub_pull_context = zmq.asyncio.Context()
        self.pull_socket = self.pub_pull_context.socket(zmq.PULL)
        try:
            self.pull_socket.bind('tcp://*:5556')
        except zmq.error.ZMQError as err:
            logging.exception('Address 5556 in use. Is another instance running?')
            error = 'Failed to bind socket'
            raise OSError(error) from err

        self.pub_socket = self.pub_pull_context.socket(zmq.PUB)

        try:
            self.pub_socket.bind('tcp://127.0.0.1:5557')
        except zmq.error.ZMQError as err:
            logging.exception('Address 5557 in use. Is another instance running?')
            error = 'Failed to bind socket'
            raise OSError(error) from err

        self._run_background(self.listen_for_push_messages())
        super().init_async()

    def stop(self) -> None:
        self.pub_socket.close()
        self.pull_socket.close()
        self.pub_pull_context.term()
        super().stop()

    def publish_message(self, topic, message):
        self.pub_socket.send_multipart([topic, message])

    async def listen_for_push_messages(self):
        """Continuously checks for incoming messages"""
        while True:
            topic, message = await self.pull_socket.recv_multipart()
            self.publish_message(topic, message)
