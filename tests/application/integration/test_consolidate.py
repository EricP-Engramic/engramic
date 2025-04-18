import logging
import sys

import pytest

from engramic.application.consolidate.consolidate_service import ConsolidateService
from engramic.application.message.message_service import MessageService
from engramic.core.host import Host
from engramic.infrastructure.system.service import Service

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info('Using Python interpreter:%s', sys.executable)


class MiniService(Service):
    def __init__(self, host) -> None:
        super().__init__(host)

    def start(self) -> None:
        self.subscribe(Service.Topic.ENGRAM_COMPLETE, self.callback_test)
        self.run_task(self.send_messages())

    async def send_messages(self) -> None:
        observation = self.host.mock_data_collector['CodifyService-0-output']
        self.send_message_async(Service.Topic.SET_TRAINING_MODE, {'training_mode': True})
        self.send_message_async(Service.Topic.OBSERVATION_COMPLETE, observation)

    def callback_test(self, generated_response_in) -> None:
        expected_results = self.host.mock_data_collector['ConsolidateService-0-output']['engram_array']
        generated_response = generated_response_in['engram_array']

        assert len(generated_response) == len(expected_results), (
            f'Result count mismatch: ' f'{len(generated_response)} generated vs {len(expected_results)} expected'
        )

        # Created date is expected to be different.
        # Indices don't compare well because of floats.
        def strip_fields(data):
            return [{k: v for k, v in item.items() if k not in {'created_date', 'indices'}} for item in data]

        stripped_generated = strip_fields(generated_response)
        stripped_expected = strip_fields(expected_results)

        gen_str = str(stripped_generated)
        exp_str = str(stripped_expected)

        assert gen_str == exp_str

        self.host.trigger_shutdown()


@pytest.mark.timeout(10)  # seconds
def test_response_service_submission() -> None:
    host = Host('mock', [MessageService, ConsolidateService, MiniService])

    host.wait_for_shutdown()
