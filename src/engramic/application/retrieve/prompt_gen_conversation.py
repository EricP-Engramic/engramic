# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

import logging

from mako.exceptions import text_error_template
from mako.template import Template

from engramic.core.prompt import Prompt


class PromptGenConversation(Prompt):
    def render_prompt(self) -> str:
        try:
            return_str = Template("""
    <instructions>
    Your name is Engramic and you are in a conversation with the user. A reference to "you" means Engramic. Review the current_user_input and provide the current user intent and a description of your working memory.

    You have access to tools to perform tasks on behalf of the user. The user may imply the use of a tool by asking you to use the tool.

    <previous_exchange>
        Previous Input
        Previous Response
    </previous_exchange>
    <current_exchange>
        Current User Input
        <you are currently at this point in the converation>
        Current Response
    <current_exchange>

    % if selected_repos is not None and repo_ids_filters is not None and all_repos is not None:
        Repos hold files that the user is interested in. The user has selected the following repos:
        % for repo_id in repo_ids_filters:
            ${all_repos[repo_id]}
        % endfor
    % endif

    Context is particularly important. It should contain clues that grounds the information in it's setting. For example, a title or header, grounds a paragraph, adding vital context to the purpose of the paragraph.

    The types of working memory include keyword phrases, integers, floats, or arrays, but never sentences or long strings over 10 words.

    % if history:
    The results of the previous exchange are provided below. Use those results to update user intent and synthisize working memory into variables.
    % endif

    user_intent:str - Write in dense keywords what the current user input is really intending which may not explicitly be stated and should be inferred from the current_user_input and all of the data in the previous_exchange especially each previous_user_intent. If the user is asking for a tool, include that request in the intent.

    This should be keyword rich, omitting filler words while capturing import details and stated as a first person instruction on what Engramic should do.

    working_memory - Update working memory which is register of variables you will use to track all elements of the conversation. If there are no changes to make on any step, or if the data referenced doesn't exist, respond with changes = None. Write each step as densely as you can, but make sure you maintain context and scope by wrapping related topics:

    memory{topic = {variable1:value1,varaiable2:value2}}

    To update working memory, you need to perform the following:

    Steps
    1. Write variables from engramic_previous_working memory and update the values based on the extrapolated values in current_user_input.
    2. Add as many new state variables and values that you can by predicting what you may track and then extraploate them from the current_user_input and engramic_previous_response. Add any new instructions you are given.
    3. Drawing from the previous_working_memory, write and update the state of all variables not changed in steps 1 and 2. Stop and think at this step as there may be logic required to determine if state 3 has cascading changes due to changes in state 1 & 2.
    4. In order, and starting with a json object called, "memory" combine the states above from 1, 2, and 3. If there are conflicting data, 3 overwrites values from 2, and 2 overwrites values from 1.


    </instructions>
    <input>
        <current_user_input>
            ${prompt_str}
        </current_user_input>
        <previous_exchange>
        % for ctr, item in enumerate(history):
            <timestamp time="${item['response_time']}">
                <user_previous_prompt>
                    ${item['prompt']['prompt_str']}
                </user_previous_prompt>
                <engramic_previous_working_memory>
                    <previous_user_intent>
                        ${item['retrieve_result']['conversation_direction']['current_user_intent']}
                    </previous_user_intent>
                    <previous_working_memory>
                        ${item['retrieve_result']['conversation_direction']['working_memory']}
                    </previous_working_memory>
                </engramic_previous_working_memory>
                % if ctr <= 3:
                    <engramic_previous_response>
                        ${item['response']}
                    </engramic_previous_response>
                % endif
            </timestamp>
        </previous_exchange>
        % endfor
    </input>


    Display your response including user_intent and working memory steps 1 through 4.
    Step 1, 2, and 3 should be dense and condensed
    Step 4 should be written in json and you should expand steps 1-3 into variables.

    """).render(**self.input_data)
        except Exception:
            error_message = text_error_template().render()
            logging.exception(error_message)
        return str(return_str)
