from dataclasses import asdict
import os
from pathlib import Path
import socket
import struct
import tempfile
from threading import Thread
import unittest
from unittest.mock import patch

from trustbound.adversarial import build_driver, parse_challenges, REQUIREMENT_ID
from trustbound.contracts import ExecutionResult
from trustbound.runner import IMAGE, sha256
from trustbound.runner_ipc import MAX_REQUEST, MAX_RESPONSE, read_message, run_through_worker, write_message
from trustbound.runner_worker import execute_request
from trustbound.service import ROOT, TASK, run_task


CODE = (ROOT / "fixtures/billing/fixed.py").read_bytes()
PUBLIC = (ROOT / "fixtures/billing/public_tests.py").read_bytes()


def request(phase="public", code=CODE):
    return {"task_id": TASK.task_id, "phase": phase, "candidate": code.decode(),
            "candidate_sha256": sha256(code)}


def evidence(code, tests, phase, timeout, **kwargs):
    return ExecutionResult(phase, "trustbound-test", IMAGE, sha256(code), sha256(tests),
                           "EXITED", 0, "ok", "", None, True, True, True)


class RunnerWorkerTests(unittest.TestCase):
    @patch("trustbound.runner_worker._execute_fixed_tests", side_effect=evidence)
    def test_runner_selects_trusted_tests_and_preserves_timeout_fixture(self, execute):
        timeout_code = (ROOT / "fixtures/billing/timeout.py").read_bytes()
        execute_request(request(code=timeout_code))
        self.assertEqual(execute.call_args.args, (timeout_code, PUBLIC, "public", TASK.timeout_seconds))
        result = execute_request(request("acceptance"))
        self.assertEqual(result.test_hash, sha256((ROOT / "acceptance/billing_v1.py").read_bytes()))

    @patch("trustbound.runner_worker._execute_fixed_tests", side_effect=evidence)
    def test_worker_rebuilds_the_exact_driver_for_filtered_cases(self, execute):
        # Invalid first item leaves a gap in the existing challenge IDs.
        rows = parse_challenges(
            '{"challenges":[{},{"amount":"1.00499","requirement_id":"'
            + REQUIREMENT_ID + '","reason":"rounding"}]}')
        cases = [{"id": rows[1].challenge.challenge_id, "amount": rows[1].challenge.amount}]
        result = execute_request(dict(request("adversarial"), cases=cases))
        self.assertEqual(result.test_hash, sha256(build_driver(rows)))

    @patch("trustbound.runner_worker._execute_fixed_tests")
    def test_rejects_arbitrary_scripts_bad_hash_and_bad_cases_before_docker(self, execute):
        for invalid in (
            dict(request(), tests="print(123)"),
            dict(request(), candidate_sha256="wrong"),
            request(code=b"print('forge')"),
            dict(request("adversarial"), cases=[{"id": "challenge-1", "amount": "nan"}]),
            dict(request("adversarial"), cases=[{"id": "challenge-1", "amount": "1", "expected": 1}]),
        ):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                execute_request(invalid)
        execute.assert_not_called()

    @patch("trustbound.runner_worker._execute_fixed_tests")
    def test_excessive_logs_produce_error_evidence(self, execute):
        result = asdict(evidence(CODE, PUBLIC, "public", 3))
        execute.return_value = ExecutionResult(**dict(result, stdout="x" * 40_000))
        execution = execute_request(request())
        self.assertEqual(execution.status, "ERROR")
        self.assertEqual(execution.error, "RUNNER_OUTPUT_LIMIT_EXCEEDED")


class RunnerIPCTests(unittest.TestCase):
    def test_oversized_frame_rejected_without_waiting_for_body(self):
        reader, writer = socket.socketpair()
        with reader, writer:
            writer.sendall(struct.pack("!I", MAX_REQUEST + 1))
            with self.assertRaisesRegex(ValueError, "exceeds size limit"):
                read_message(reader, MAX_REQUEST, 1)

    def test_socket_round_trip_and_hash_binding(self):
        for valid in (True, False):
            with self.subTest(valid=valid):
                seen = []
                client, worker_socket = socket.socketpair()

                def respond():
                    with worker_socket:
                        seen.append(read_message(worker_socket, MAX_REQUEST, 3))
                        reply = asdict(evidence(CODE, PUBLIC, "public", 3))
                        if not valid:
                            reply["test_hash"] = "wrong"
                        write_message(worker_socket, reply, MAX_RESPONSE, 3)

                worker = Thread(target=respond)
                worker.start()
                try:
                    with (patch.dict(os.environ, {"TRUSTBOUND_RUNNER_SOCKET": "/run/test.sock"}),
                          patch("trustbound.runner_ipc._connect", return_value=client)):
                        result = run_through_worker(CODE, PUBLIC, "public")
                finally:
                    worker.join(6)
                self.assertEqual(seen, [request()])
                self.assertEqual(result.status, "EXITED" if valid else "ERROR")

    @patch("trustbound.service._execute_fixed_tests")
    def test_unavailable_worker_does_not_fall_back_to_web_docker(self, local_docker):
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "missing.sock")
            with patch.dict(os.environ, {"TRUSTBOUND_RUNNER_SOCKET": path}):
                report = run_task(TASK.task_id, "fixed")
        self.assertEqual(report.status, "INCONCLUSIVE")
        self.assertEqual(report.executions[0].error, "RUNNER_IPC_EVIDENCE_UNAVAILABLE")
        local_docker.assert_not_called()
