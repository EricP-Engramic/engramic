# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

import logging
from enum import Enum

import zmq
import zmq.asyncio

from engramic.core.host import Host
from engramic.core.metrics_tracker import MetricsTracker
from engramic.infrastructure.system import Service


class MessageMetric(Enum):
    MESSAGE_RECIEVED = 'message_recieved'
    MESSAGE_SENT = 'message_sent'


class BaseMessageService(Service):
    def __init__(self, host: Host) -> None:
        super().__init__(host)
        self.metrics_tracker: MetricsTracker[MessageMetric] = MetricsTracker[MessageMetric]()

    def init_async(self) -> None:
        super().init_async()
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

        self.run_background(self.listen_for_push_messages())

    def stop(self) -> None:
        self.pub_socket.close()
        self.pull_socket.close()
        self.pub_pull_context.term()
        super().stop()

    async def listen_for_push_messages(self) -> None:
        """Continuously checks for incoming messages"""
        while not self.recieved_stop_message:
            topic, message = await self.pull_socket.recv_multipart()
            self.metrics_tracker.increment(MessageMetric.MESSAGE_RECIEVED)
            self.pub_socket.send_multipart([topic, message])
            self.metrics_tracker.increment(MessageMetric.MESSAGE_SENT)
