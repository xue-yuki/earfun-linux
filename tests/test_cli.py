import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock

from earfun_cli.cli import OperationError, query_values, set_eq, set_feature
from earfun_cli.protocol import BATTERY, CASE_BATTERY, FEATURES, Frame
from earfun_cli.transport import TransportError

ENTRY = Path(__file__).resolve().parents[1] / "earfunctl.py"


class CliTests(unittest.TestCase):
    def run_cli(self, *arguments):
        with tempfile.TemporaryDirectory() as config_root:
            result = subprocess.run([sys.executable, str(ENTRY), *arguments, "--json"],
                                    capture_output=True, text=True,
                                    env={**os.environ, "XDG_CONFIG_HOME": config_root})
        return result.returncode, json.loads(result.stdout)

    def test_dry_run_needs_no_mac_and_accepts_common_flags_after_command(self):
        code, result = self.run_cli("noise", "anc", "--dry-run")
        self.assertEqual(code, 0)
        self.assertTrue(result["dry_run"])
        self.assertEqual(result["frames"][0]["frame"], "ef2085010304fe")
        self.assertEqual(result["frames"][1]["frame"], "ef20800000fe")

    def test_common_flags_before_command_are_preserved(self):
        code, result = self.run_cli("--dry-run", "game", "on")
        self.assertEqual(code, 0)
        self.assertTrue(result["dry_run"])

    def test_eq_flat_builds_ten_frames(self):
        code, result = self.run_cli("eq", "--preset", "flat", "--dry-run")
        self.assertEqual(code, 0)
        self.assertEqual(len(result["frames"]), 10)

    def test_invalid_eq_exits_with_actionable_error(self):
        code, result = self.run_cli("eq", "--gains=0,0,0", "--dry-run")
        self.assertEqual(code, 2)
        self.assertIn("exactly 10", result["error"])

    def test_decode_captured_battery(self):
        code, result = self.run_cli("decode", "ef101402504698fe")
        self.assertEqual(code, 0)
        self.assertEqual(result["frames"][0]["decoded"]["left"]["percent"], 80)

    def test_missing_mac_is_not_automatic_selection(self):
        code, result = self.run_cli("status")
        self.assertEqual(code, 2)
        self.assertIn("--mac", result["error"])

    def test_partial_status_retains_success_and_error(self):
        session = Mock()
        session.query.side_effect = [Frame(BATTERY, b"\x50\x46"), TransportError("case unavailable")]
        result = query_values(session, [("earbuds", BATTERY), ("case", CASE_BATTERY)])
        self.assertFalse(result["ok"])
        self.assertEqual(result["status"], "partial")
        self.assertIn("earbuds", result["values"])
        self.assertIn("case", result["errors"])

    def test_write_readback_mismatch_is_failure(self):
        session = Mock()
        session.query.return_value = Frame(FEATURES["noise"].get_opcode, b"\x01")
        result = set_feature(session, "noise", "anc")
        self.assertFalse(result["ok"])
        self.assertFalse(result["verified"])
        self.assertTrue(result["transport_sent"])

    def test_write_readback_success_requires_matching_observed_value(self):
        session = Mock()
        session.query.return_value = Frame(FEATURES["noise"].get_opcode, b"\x03")
        self.assertTrue(set_feature(session, "noise", "anc")["verified"])

    def test_write_with_no_readback_retains_uncertainty(self):
        session = Mock(); session.query.side_effect = TransportError("timeout")
        with self.assertRaises(OperationError) as caught:
            set_feature(session, "game", "on")
        self.assertTrue(caught.exception.details["transport_sent"])
        self.assertFalse(caught.exception.details["verified"])

    def test_partial_eq_reports_completed_bands(self):
        session = Mock()
        session.send.side_effect = [None, None, OSError("link lost")]
        with self.assertRaises(OperationError) as caught:
            set_eq(session, [0] * 10)
        self.assertEqual(caught.exception.details["bands_transport_sent"], 2)
        self.assertFalse(caught.exception.details["device_state_verified"])

    def test_complete_eq_is_not_claimed_verified(self):
        result = set_eq(Mock(), [0] * 10)
        self.assertEqual(result["status"], "transport_sent_unverified")
        self.assertFalse(result["device_state_verified"])


if __name__ == "__main__":
    unittest.main()
