import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from earfun_cli.cli import main
from earfun_cli.config import load_config, save_config
from service.backend import Backend, merge_result, new_state, request_args
from install import unit_text

CONFIG = {'mac': '02:00:00:00:00:01', 'channel': 1}


class BackendTests(unittest.TestCase):
    def test_allowlist_blocks_invalid_request_before_runner(self):
        run = Mock()
        backend = Backend(CONFIG, runner=run)
        for command, value in [('reset', ''), ('noise', 'invalid'), ('eq', '../x'), ('status', 'on')]:
            with self.assertRaises(ValueError):
                backend.request(command, value)
        run.assert_not_called()

    def test_disconnected_device_never_receives_writes(self):
        run = Mock()
        backend = Backend(CONFIG, runner=run, connection_check=lambda: {'connected': False})
        self.assertFalse(backend.request('noise', 'anc')['ok'])
        run.assert_not_called()

    def test_backend_preserves_verified_feature_and_unverified_eq(self):
        run = Mock(return_value={'ok': True, 'verified': True})
        backend = Backend(CONFIG, runner=run)
        self.assertTrue(backend.request('noise', 'anc')['verified'])
        self.assertEqual(run.call_args.args[0].value, 'anc')
        run.return_value = {'ok': True, 'device_state_verified': False}
        result = backend.request('eq', 'bass')
        self.assertFalse(result['device_state_verified'])
        self.assertEqual(run.call_args.args[0].preset, 'bass')

    def test_disconnect_clears_old_battery(self):
        state = {**new_state(CONFIG), 'connected': True, 'values': {'case': {'data': {'percent': 50}}}}
        state = merge_result(state, 'status', {'ok': False, 'device_info': {'connected': False}}, 1)
        self.assertEqual(state['values'], {})

    def test_failed_status_field_does_not_show_old_success(self):
        state = {**new_state(CONFIG), 'connected': True, 'values': {'noise': {'data': {'value': 'anc'}}}}
        result = {'ok': False, 'values': {}, 'errors': {'noise': 'timeout'}, 'device_info': {'connected': True}}
        state = merge_result(state, 'status', result, 1)
        self.assertEqual(state['values'], {})
        self.assertIn('timeout', state['error'])

    def test_failed_readback_removes_old_feature(self):
        state = {**new_state(CONFIG), 'connected': True, 'values': {'noise': {'data': {'value': 'anc'}}}}
        state = merge_result(state, 'noise', {'ok': False, 'error': 'timeout'}, 2)
        self.assertNotIn('noise', state['values'])

    def test_unknown_mode_is_preserved(self):
        state = {**new_state(CONFIG), 'connected': True}
        observed = {'known': False, 'value': None, 'raw_value': 8}
        state = merge_result(state, 'noise', {'ok': False, 'observed': observed}, 2)
        self.assertFalse(state['values']['noise']['data']['known'])
        self.assertIsNotNone(state['error'])

    def test_bluez_failure_does_not_claim_a_confirmed_disconnect(self):
        result = {'ok': False, 'error': 'BlueZ unavailable', 'connection_check_failed': True,
                  'device_info': {'connected': False}}
        state = merge_result(new_state(CONFIG), 'status', result, 2)
        self.assertFalse(state['connection_checked'])

    def test_unit_escaping(self):
        text = unit_text(Path('/tmp/a "b%/service.py'))
        self.assertIn('a \\"b%%/service.py', text)
        with self.assertRaises(ValueError):
            unit_text(Path('/tmp/a\nb/service.py'))


class ConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'XDG_CONFIG_HOME': self.temp.name})
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_config_roundtrip_and_private_mode(self):
        self.assertEqual(load_config(), {})
        save_config(**CONFIG)
        self.assertEqual(load_config(), CONFIG)
        self.assertEqual((Path(self.temp.name) / 'earfun/config.json').stat().st_mode & 0o777, 0o600)

    def test_rejects_invalid_channel_without_saving(self):
        for channel in (0, 31, True, '1'):
            with self.assertRaises(ValueError):
                save_config(CONFIG['mac'], channel)
        self.assertEqual(load_config(), {})

    def test_cli_uses_default_and_never_inherits_channel_for_different_mac(self):
        save_config(**CONFIG)
        for argv, expected in [(['status'], CONFIG), (['--mac', '11:22:33:44:55:66', 'status'], {'mac': '11:22:33:44:55:66'})]:
            with patch('earfun_cli.cli.execute', return_value={'ok': True}) as run, contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(argv), 0)
            args = run.call_args.args[0]
            self.assertEqual(args.mac, expected['mac'])
            self.assertEqual(getattr(args, 'channel', None), expected.get('channel'))

    def test_explicit_channel_wins(self):
        save_config(**CONFIG)
        with patch('earfun_cli.cli.execute', return_value={'ok': True}) as run, contextlib.redirect_stdout(io.StringIO()):
            main(['status', '--channel', '7'])
        self.assertEqual(run.call_args.args[0].channel, 7)


if __name__ == '__main__':
    unittest.main()
