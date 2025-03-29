# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

import os
from typing import Any, cast, no_type_check

from google import genai
from google.genai import types
from pydantic import BaseModel, create_model

from engramic.core.interface.llm import LLM
from engramic.core.prompt import Prompt
from engramic.infrastructure.system.plugin_specifications import llm_impl
from engramic.infrastructure.system.websocket_manager import WebsocketManager


class Gemini(LLM):
    def __init__(self) -> None:
        api_key = os.environ.get('GEMINI_API_KEY')
        self._api_client = genai.Client(api_key=api_key)

    @no_type_check
    def create_pydantic_model(self, name: str, fields: dict[str, type[Any]]) -> type[BaseModel]:
        model_fields = {key: (field_type, ...) for key, field_type in fields.items()}
        model: Any = create_model(name, **model_fields)
        return cast(type[BaseModel], model)

    @llm_impl
    def submit(self, prompt: Prompt, structured_schema: dict[str, Any], args: dict[str, str]) -> dict[str, Any]:
        model = args['model']

        contents = [
            types.Content(
                role='user',
                parts=[
                    types.Part.from_text(text=prompt.render_prompt()),
                ],
            ),
        ]

        if structured_schema is not None:
            pydantic_model = self.create_pydantic_model('dynamic_model', structured_schema)

            generate_content_config = types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type='application/json',
                response_schema=pydantic_model,
            )
        else:
            generate_content_config = types.GenerateContentConfig(
                temperature=1,
                top_p=0.95,
                top_k=40,
                max_output_tokens=8192,
                response_mime_type='text/plain',
            )

        response = self._api_client.models.generate_content(
            model=model,
            contents=contents,
            config=generate_content_config,
        )

        ret_string = response.text

        if ret_string.startswith('```toml') and ret_string.endswith('```'):
            ret_string = ret_string[7:-3]

        return {'llm_response': ret_string}

    @llm_impl
    def submit_streaming(
        self, prompt: Prompt, args: dict[str, str], websocket_manager: WebsocketManager
    ) -> dict[str, str]:
        del args
        model = 'gemini-2.0-flash'
        contents = [
            types.Content(
                role='user',
                parts=[
                    types.Part.from_text(text=prompt.render_prompt()),
                ],
            ),
        ]

        generate_content_config = types.GenerateContentConfig(
            temperature=1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=8192,
            response_mime_type='text/plain',
        )

        response = self._api_client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        )

        full_response = ''
        for chunk in response:
            websocket_manager.send_message(LLM.StreamPacket(chunk, False, ''))
            full_response += chunk.text

        return {'llm_response': full_response}
