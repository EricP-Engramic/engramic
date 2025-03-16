# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

from abc import ABC, abstractmethod
from dataclasses import dataclass

from engramic.infrastructure.system.websocket_manager import WebsocketManager


class LLM(ABC):
    """
    An abstract base class that defines an interface for any Large Language Model.
    """
    @dataclass()
    class StreamPacket():
        packet: str
        finish:bool
        finish_reason:str


    @abstractmethod
    def submit(self, prompt: str, args:dict ) -> str:
        """
        Submits a prompt to the LLM and returns the model-generated text.

        Args:
            prompt (str): The prompt or input text for the LLM.
            **kwargs (Any): Optional keyword arguments for provider-specific settings,
                such as model name, temperature, max tokens, etc.

        Returns:
            str: The model-generated response.
        """

    @abstractmethod
    def submit_streaming(self, prompt: str, args:dict, websocket_manager:WebsocketManager ) -> str:
        """
        Submits a prompt to the LLM and returns the model-generated text.

        Args:
            prompt (str): The prompt or input text for the LLM.
            **kwargs (Any): Optional keyword arguments for provider-specific settings,
                such as model name, temperature, max tokens, etc.

        Returns:
            str: The model-generated response.
        """