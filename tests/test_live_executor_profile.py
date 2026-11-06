import os
import unittest
from unittest.mock import patch

from trustbound.service import TASK
from trustbound.web_tasks import _execute_base_run


class LiveExecutorProfileTests(unittest.TestCase):
    @patch.dict(os.environ, {"TRUSTBOUND_EXECUTOR_SINGLE_PROPOSAL": "1"})
    @patch("trustbound.web_tasks.run_executor", return_value={"source": "test", "status": "test", "error": None})
    @patch("trustbound.web_tasks.VultrClient")
    def test_opt_in_reserves_room_for_the_proposal_and_preserves_offline_executor(self, client, execute):
        _execute_base_run(TASK.task_id, "live_executor", None)
        client.assert_called_once_with(timeout=60, max_attempts=1, output_limit=4096)
        execute.assert_called_once_with(client.return_value, smoke_check=False, proposal_tokens=4096,
                                        reasoning_tokens=1536)

        client.reset_mock()
        execute.reset_mock()
        with patch("trustbound.web_tasks.offline_client") as offline:
            _execute_base_run(TASK.task_id, "offline_executor", "fixed")
        client.assert_not_called()
        execute.assert_called_once()
        self.assertIs(execute.call_args.args[0], offline.return_value)
        self.assertNotIn("proposal_tokens", execute.call_args.kwargs)
