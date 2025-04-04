# Copyright (c) 2025 Preisz Consulting, LLC.
# This file is part of Engramic, licensed under the Engramic Community License.
# See the LICENSE file in the project root for more details.
import os
import uuid
from collections.abc import Sequence
from multiprocessing import Lock
from typing import Any, cast

import chromadb
from chromadb.config import Settings

from engramic.core.index import Index
from engramic.core.interface.vector_db import VectorDB
from engramic.infrastructure.system.plugin_specifications import vector_db_impl


class ChromaDB(VectorDB):
    DEFAULT_THRESHOLD = 0.5
    DEFAULT_N_RESULTS = 2

    def __init__(self) -> None:
        self.multi_process_lock = Lock()

        db_path = os.path.join('local_storage', 'chroma_db')

        local_storage_root_path = os.getenv('LOCAL_STORAGE_ROOT_PATH')
        if local_storage_root_path is not None:
            db_path = os.path.join(local_storage_root_path, 'chroma_db')

        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.client = chromadb.PersistentClient(
            path='local_storage/chroma_db', settings=Settings(anonymized_telemetry=False)
        )
        self.collection = {}
        self.collection['main'] = self.client.get_or_create_collection(name='main')
        self.collection['meta'] = self.client.get_or_create_collection(name='meta')

    @vector_db_impl
    def query(self, collection_name: str, embeddings: list[float], args: dict[str, Any]) -> dict[str, Any]:
        embeddings_typed: Sequence[float] = embeddings
        n_results = self.DEFAULT_N_RESULTS
        threshold: float = self.DEFAULT_THRESHOLD

        if args.get('threshold') is not None:
            threshold = args['threshold']

        if args.get('threshold') is not None:
            n_results = args['n_results']

        with self.multi_process_lock:
            results = self.collection[collection_name].query(query_embeddings=embeddings_typed, n_results=n_results)

        distances = cast(list[list[float]], results['distances'])[0]
        documents = cast(list[list[str]], results['documents'])[0]

        ret_ids = []
        for i, distance in enumerate(distances):
            if distance < threshold:
                ret_ids.append(documents[i])

        return {'query_set': set(ret_ids)}

    @vector_db_impl
    def insert(self, collection_name: str, index_list: list[Index], obj_id: str, args: dict[str, Any]) -> None:
        del args

        documents = []
        embeddings = []
        ids = []

        for embedding in index_list:
            documents.append(obj_id)
            embeddings.append(cast(Sequence[float], embedding.embedding))
            ids.append(str(uuid.uuid4()))

        with self.multi_process_lock:
            self.collection[collection_name].add(documents=documents, embeddings=embeddings, ids=ids)
