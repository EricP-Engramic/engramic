# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

from dataclasses import dataclass

from engramic.core import Prompt, PromptAnalysis
from engramic.core.retrieve_result import RetrieveResult


@dataclass
class Response:
    id: str
    response: str
    retrieve_result: RetrieveResult
    prompt: Prompt
    analysis: PromptAnalysis
