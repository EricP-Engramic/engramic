# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.

import asyncio
import json
import logging
import time
from concurrent.futures import Future
from dataclasses import asdict
from enum import Enum
from typing import TYPE_CHECKING, Any

from engramic.application.consolidate.prompt_gen_indices import PromptGenIndices
from engramic.core import Engram, Index
from engramic.core.host import Host
from engramic.core.metrics_tracker import MetricPacket, MetricsTracker
from engramic.core.observation import Observation
from engramic.infrastructure.repository.observation_repository import ObservationRepository
from engramic.infrastructure.system.service import Service

if TYPE_CHECKING:
    from engramic.infrastructure.system.plugin_manager import PluginManager


class ConsolidateMetric(Enum):
    OBSERVATIONS_RECIEVED = 'observations_recieved'
    SUMMARIES_GENERATED = 'summaries_generated'
    ENGRAMS_GENERATED = 'engrams_generated'
    INDICES_GENERATED = 'indices_generated'
    EMBEDDINGS_GENERATED = 'embeddings_generated'


class ConsolidateService(Service):
    """
    The ConsolidateService orchestrates the post-processing pipeline for completed observations,
    coordinating summarization, engram generation, index generation, and embedding creation.

    This service is triggered when an observation is marked complete and is responsible for the following:

    1. **Summarization** - Generates a natural language summary from the observation using an LLM plugin.
    2. **Embedding Summaries** - Uses an embedding plugin to create vector embeddings of the summary text.
    3. **Engram Generation** - Extracts or constructs engrams from the observation's content.
    4. **Index Generation** - Applies an LLM to generate meaningful textual indices for each engram.
    5. **Embedding Indices** - Uses an embedding plugin to convert each index into a vector representation.
    6. **Publishing Results** - Emits messages like `ENGRAM_COMPLETE`, `META_COMPLETE`, and `INDEX_COMPLETE` at various stages to notify downstream systems.

    Metrics are tracked throughout the pipeline using a `MetricsTracker` and returned on demand via the
    `on_acknowledge` method.

    Attributes:
        plugin_manager (PluginManager): Manages access to all system plugins.
        llm_summary (dict): Plugin used for generating summaries.
        llm_gen_indices (dict): Plugin used for generating indices from engrams.
        embedding_gen_embed (dict): Plugin used for generating embeddings for summaries and indices.
        db_document (dict): Plugin for document-level database access.
        observation_repository (ObservationRepository): Handles deserialization of incoming observations.
        engram_builder (dict[str, Engram]): In-memory store of engrams awaiting completion.
        index_builder (dict[str, Index]): In-memory store of indices being constructed.
        metrics_tracker (MetricsTracker): Tracks metrics across each processing stage.

    Methods:
        start(): Subscribes the service to message topics.
        stop(): Stops the service and clears subscriptions.
        on_observation_complete(observation_dict): Handles post-processing when an observation completes.
        _ generate_summary(observation): Creates a summary of the observation content. (not implemented yet)
        on_summary(summary_fut): Callback after summary generation completes.
        generate_summary_embeddings(meta): Generates and attaches embeddings for a summary.
        generate_engrams(observation): Constructs engrams from observation data.
        on_engrams(engram_list_fut): Callback after engram generation; handles index and embedding creation.
        gen_indices(index, id_in, engram): Uses an LLM to create indices from an engram.
        gen_embeddings(id_and_index_dict, process_index): Creates embeddings for generated indices.
        on_acknowledge(message_in): Sends a metrics snapshot for observability/debugging.
    """

    def __init__(self, host: Host) -> None:
        super().__init__(host)
        self.plugin_manager: PluginManager = host.plugin_manager
        self.llm_summary: dict[str, Any] = self.plugin_manager.get_plugin('llm', 'summary')
        self.llm_gen_indices: dict[str, Any] = self.plugin_manager.get_plugin('llm', 'gen_indices')
        self.embedding_gen_embed: dict[str, Any] = self.plugin_manager.get_plugin('embedding', 'gen_embed')
        self.db_document: dict[str, Any] = self.plugin_manager.get_plugin('db', 'document')
        self.observation_repository = ObservationRepository(self.db_document)
        self.engram_builder: dict[str, Engram] = {}
        self.metrics_tracker: MetricsTracker[ConsolidateMetric] = MetricsTracker[ConsolidateMetric]()

    def start(self) -> None:
        self.subscribe(Service.Topic.OBSERVATION_COMPLETE, self.on_observation_complete)
        self.subscribe(Service.Topic.ACKNOWLEDGE, self.on_acknowledge)
        super().start()

    async def stop(self) -> None:
        await super().stop()

    def on_observation_complete(self, observation_dict: dict[str, Any]) -> None:
        if __debug__:
            self.host.update_mock_data_input(self, observation_dict, observation_dict['source_id'])

        # print("run consolidate")
        # should run a task for this.
        observation = self.observation_repository.load_dict(observation_dict)
        self.metrics_tracker.increment(ConsolidateMetric.OBSERVATIONS_RECIEVED)

        self.run_task(self._generate_summary_embeddings(observation))

        generate_engrams = self.run_task(self._generate_engrams(observation))
        generate_engrams.add_done_callback(self.on_engrams)

    """
    ### Generate meta embeddings
    """

    async def _generate_summary_embeddings(self, observation: Observation) -> None:
        if observation.meta.summary_full is None:
            error = 'Summary full is none.'
            raise ValueError(error)

        plugin = self.embedding_gen_embed
        embedding_list_ret = await asyncio.to_thread(
            plugin['func'].gen_embed,
            strings=[observation.meta.summary_full.text],
            args=self.host.mock_update_args(plugin, 0, observation.source_id),
        )

        self.host.update_mock_data(plugin, embedding_list_ret, 0, observation.source_id)

        embedding_list = embedding_list_ret[0]['embeddings_list']
        observation.meta.summary_full.embedding = embedding_list[0]

        self.send_message_async(Service.Topic.META_COMPLETE, asdict(observation.meta))

    """
    ### Generate Engrams

    Create engrams from the observation.
    """

    async def _generate_engrams(self, observation: Observation) -> Observation:
        self.metrics_tracker.increment(ConsolidateMetric.ENGRAMS_GENERATED, len(observation.engram_list))

        return observation

    def on_engrams(self, observation_fut: Future[Any]) -> None:
        observation = observation_fut.result()
        engram_list = observation.engram_list
        source_id = observation.source_id

        engram_ids = [engram.id for engram in engram_list]

        self.send_message_async(Service.Topic.ENGRAM_CREATED, {'source_id': source_id, 'engram_id_array': engram_ids})

        # Keep references so we can fill them in later
        for engram in engram_list:
            if self.engram_builder.get(engram.id) is None:
                self.engram_builder[engram.id] = engram
            else:
                error = 'Engram ID Collision. During conslidation, two Engrams with the same IDs were detected.'
                raise RuntimeError(error)

        # 1) Generate indices for each engram
        index_tasks = [self._gen_indices(i, engram.id, source_id, engram) for i, engram in enumerate(engram_list)]

        indices_future = self.run_tasks(index_tasks)

        indices_future.add_done_callback(self.on_indices_done)

    async def _gen_indices(self, index: int, id_in: str, source_id: str, engram: Engram) -> dict[str, Any]:
        data_input = {'engram': engram}

        prompt = PromptGenIndices(prompt_str='', input_data=data_input)
        plugin = self.llm_gen_indices

        response_schema = {'index_text_array': list[str]}

        indices = await asyncio.to_thread(
            plugin['func'].submit,
            prompt=prompt,
            structured_schema=response_schema,
            args=self.host.mock_update_args(plugin, index, source_id),
            images=None,
        )

        load_json = json.loads(indices[0]['llm_response'])
        response_json: dict[str, Any] = {'index_text_array': []}

        # generate context
        context_string = 'Context: '

        if engram.context is None:
            error = 'None context found in engram.'
            raise RuntimeError(error)

        for item, key in engram.context.items():
            if key != 'null':
                context_string += f'{item}: {key}\n'

        # add in the context to each index.
        for index_item in load_json['index_text_array']:
            response_json['index_text_array'].append(context_string + ' Content: ' + index_item)

        self.host.update_mock_data(plugin, indices, index, source_id)

        self.metrics_tracker.increment(ConsolidateMetric.INDICES_GENERATED, len(indices))

        if len(response_json['index_text_array']) == 0:
            error = 'An empty index was created.'
            raise RuntimeError(error)

        return {'id': id_in, 'source_id': source_id, 'indices': response_json['index_text_array']}

    # Once all indices are generated, generate embeddings
    def on_indices_done(self, indices_list_fut: Future[Any]) -> None:
        # This is the accumulated result of each gen_indices(...) call
        indices_list: dict[str, Any] = indices_list_fut.result()
        # indices_list should have a key like 'gen_indices' -> list[dict[str, Any]]
        index_sets: list[dict[str, Any]] = indices_list['_gen_indices']

        # for index in index_sets:
        #    indices = index['indices']
        #    for sub_index in indices:
        #        print(sub_index)

        # 2) Generate embeddings for each index set
        embed_tasks = [self._gen_embeddings(index_set, i) for i, index_set in enumerate(index_sets)]

        embed_future = self.run_tasks(embed_tasks)

        embed_future.add_done_callback(self.on_embeddings_done)

    async def _gen_embeddings(self, id_and_index_dict: dict[str, Any], process_index: int) -> dict[str, Any]:
        indices = id_and_index_dict['indices']
        engram_id: str = id_and_index_dict['id']
        source_id: str = id_and_index_dict['source_id']

        plugin = self.embedding_gen_embed

        embedding_list_ret = await asyncio.to_thread(
            plugin['func'].gen_embed, strings=indices, args=self.host.mock_update_args(plugin, process_index, source_id)
        )

        self.host.update_mock_data(plugin, embedding_list_ret, process_index, source_id)

        embedding_list = embedding_list_ret[0]['embeddings_list']

        self.metrics_tracker.increment(ConsolidateMetric.EMBEDDINGS_GENERATED, len(embedding_list))

        index_id_array = []

        # Convert raw embeddings to Index objects and attach them
        try:
            index_array: list[Index] = []
            for i, vec in enumerate(embedding_list):
                index = Index(indices[i], vec)
                index_array.append(index)
                index_id_array.append(index.id)
        except Exception:
            logging.exception('Exception caught.')

        self.send_message_async(Service.Topic.INDEX_CREATED, {'source_id': source_id, 'index_id_array': index_id_array})

        self.engram_builder[engram_id].indices = index_array
        serialized_index_array = [asdict(index) for index in index_array]

        # We can optionally notify about newly attached indices
        self.send_message_async(
            Service.Topic.INDEX_COMPLETE,
            {'index': serialized_index_array, 'engram_id': engram_id, 'source_id': source_id},
        )

        # Return the ID so we know which engram was updated
        return {'engram_id': engram_id, 'source_id': source_id}

    # Once embeddings are generated, then we're truly done
    def on_embeddings_done(self, embed_fut: Future[Any]) -> None:
        ret = embed_fut.result()  # ret should have 'gen_embeddings' -> list of engram IDs

        ret_dict = ret['_gen_embeddings']  # which IDs got their embeddings updated
        source_id = ret_dict[0]['source_id']

        # Now that embeddings exist, we can send "ENGRAM_COMPLETE" for each
        engram_dict: list[dict[str, Any]] = []
        engram_dict = [asdict(self.engram_builder[eid['engram_id']]) for eid in ret_dict]

        self.send_message_async(Service.Topic.ENGRAM_COMPLETE, {'engram_array': engram_dict, 'source_id': source_id})

        if __debug__:
            self.host.update_mock_data_output(self, {'engram_array': engram_dict}, 0, source_id)

        for eid in ret_dict:
            del self.engram_builder[eid['engram_id']]

    """
    ### Acknowledge

    Acknowledge and return metrics
    """

    def on_acknowledge(self, message_in: str) -> None:
        del message_in

        metrics_packet: MetricPacket = self.metrics_tracker.get_and_reset_packet()

        self.send_message_async(
            Service.Topic.STATUS,
            {'id': self.id, 'name': self.__class__.__name__, 'timestamp': time.time(), 'metrics': metrics_packet},
        )
