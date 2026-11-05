from dataclasses import replace
import errno
import unittest

from trustbound.attack_suite import _judge, _observations
from trustbound.contracts import ExecutionResult
from trustbound.runner import IMAGE, MEMORY_LIMIT_BYTES


BASE = ExecutionResult("attack-test", "test-only-container", IMAGE, "code", "driver",
                       "EXITED", 0, "", "", None, True, True, True)


class AttackVerdictTests(unittest.TestCase):
    def test_exit_137_without_docker_oom_flag_is_not_memory_evidence(self):
        observations = [{"allocation_started": True, "memory_max": str(MEMORY_LIMIT_BYTES),
                         "swap_max": "0"}]
        killed = replace(BASE, exit_code=137)
        self.assertEqual(_judge("A5", killed, observations)[0], "INCONCLUSIVE")
        self.assertEqual(_judge("A5", replace(killed, oom_killed=True), observations)[0], "PASS")
        self.assertEqual(_judge("A5", replace(killed, oom_killed=True), [])[0], "INCONCLUSIVE")

    def test_started_loop_requires_deadline_and_cleanup_evidence(self):
        killed = replace(BASE, exit_code=137, status="TIMED_OUT", timeout_reason="deadline")
        self.assertEqual(_judge("A4", killed, [{"loop_started": True}])[0], "PASS")
        self.assertEqual(_judge("A4", killed, [])[0], "INCONCLUSIVE")
        self.assertEqual(_judge("A4", replace(killed, cleanup_confirmed=False),
                                [{"loop_started": True}])[0], "INCONCLUSIVE")

    def test_visible_canary_is_a_failure_even_if_probe_exit_code_is_zero(self):
        observed = {"sentinel_env_visible": False, "credential_env_visible": False,
                    "host_read_errno": errno.ENOENT}
        self.assertEqual(_judge("A3", BASE, [observed])[0], "PASS")
        self.assertEqual(_judge("A3", BASE, [dict(observed, sentinel_env_visible=True)])[0], "FAIL")
        self.assertEqual(_judge("A3", BASE, [dict(observed, host_read_errno=None)])[0], "FAIL")

    def test_no_outbound_route_needs_network_namespace_evidence(self):
        observed = {"target": "192.0.2.1", "route_errno": errno.ENETUNREACH, "interfaces": ["lo"]}
        self.assertEqual(_judge("A2", BASE, [observed])[0], "PASS")
        self.assertEqual(_judge("A2", BASE, [dict(observed, interfaces=["lo", "eth0"])])[0], "FAIL")
        self.assertEqual(_judge("A2", BASE, _observations("unexpected stdout"))[0], "INCONCLUSIVE")
