# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.


import pluggy
from engramic.core.prompt import Prompt
from engramic.infrastructure.system.websocket_manager import WebsocketManager
from typing import Any

llm_impl = pluggy.HookimplMarker('llm')
llm_spec = pluggy.HookspecMarker('llm')


class LLMSpec:
    @llm_spec
    def submit(self, llm_input_prompt: Prompt, args: dict, **kwargs ) -> dict:
        del llm_input_prompt, args, callback
        """Submits an LLM request with the given prompt and arguments."""
        error_message = 'Subclasses must implement `submit`'
        raise NotImplementedError(error_message)


llm_manager = pluggy.PluginManager('llm')
llm_manager.add_hookspecs(LLMSpec)


vector_db_impl = pluggy.HookimplMarker('vector_db')
vector_db_spec = pluggy.HookspecMarker('vector_db')


class VectorDBspec:
    @vector_db_spec
    def query(self, prompt: Prompt) -> set:
        del prompt
        error_message = 'Subclasses must implement `query`'
        raise NotImplementedError(error_message)


vector_manager = pluggy.PluginManager('vector_db')
vector_manager.add_hookspecs(VectorDBspec)


db_impl = pluggy.HookimplMarker('db')
db_spec = pluggy.HookspecMarker('db')


class DBspec:
    @db_spec
    def connect(self, **kwargs: Any) -> bool:
        error_message = 'Subclasses must implement `connect`'
        raise NotImplementedError(error_message)
    
    @db_spec
    def close(close) -> bool:
        error_message = 'Subclasses must implement `close`'
        raise NotImplementedError(error_message)

    @db_spec
    def execute(self, **kwargs: Any) -> bool:
        error_message = 'Subclasses must implement `execute`'
        raise NotImplementedError(error_message)

db_manager = pluggy.PluginManager('db')
db_manager.add_hookspecs(DBspec)