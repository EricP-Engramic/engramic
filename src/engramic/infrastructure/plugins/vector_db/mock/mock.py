import logging
from typing import Any

import pluggy

from engramic.core import Index, Prompt
from engramic.core.vector_db import VectorDB
from engramic.infrastructure.system.plugin_specifications import vector_db_impl


class Mock(VectorDB):
    @vector_db_impl
    def query(self, prompt: Prompt, **kwargs: Any) -> list[str]:
        logging.info('Vector DB mock.%s %s', prompt, kwargs)
        return ['d1b847da-04eb-4846-a503-512aad2706c6', '83c5f4bb-65b1-4422-80b9-45ba43d91c21']

    @vector_db_impl
    def insert(self, index_list: list[Index]) -> None:
        for index in index_list:
            logging.info('Add embeddings. %s', index.embedding)


pm = pluggy.PluginManager('vector_db')
pm.register(Mock())
