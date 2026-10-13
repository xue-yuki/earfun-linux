"""Run inside dbus-run-session with system Python/Gio for a real session-bus test."""
import ast
import importlib.util
import json
import os
from pathlib import Path
import selectors
import shutil
import subprocess
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parent.parent

@unittest.skipUnless(importlib.util.find_spec('gi') and os.environ.get('DBUS_SESSION_BUS_ADDRESS') and shutil.which('gdbus'),
                     'Requires Gio, gdbus and an isolated session bus')
class DBusTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.process = subprocess.Popen([sys.executable, str(ROOT / 'tests/dbus_fixture.py')],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        selector = selectors.DefaultSelector()
        selector.register(cls.process.stdout, selectors.EVENT_READ)
        if not selector.select(timeout=8):
            cls.process.terminate()
            stdout, stderr = cls.process.communicate(timeout=5)
            raise RuntimeError('Fixture not ready: ' + stderr)
        if cls.process.stdout.readline().strip() != 'READY':
            cls.process.terminate()
            stdout, stderr = cls.process.communicate(timeout=5)
            raise RuntimeError('Fixture startup failed: ' + stderr)
        selector.close()
        time.sleep(0.1)

    @classmethod
    def tearDownClass(cls):
        cls.process.terminate()
        _, stderr = cls.process.communicate(timeout=5)
        if 'Traceback' in stderr or 'CRITICAL' in stderr:
            raise AssertionError(stderr)

    def call(self, method, *args):
        output = subprocess.check_output(['gdbus', 'call', '--session', '--dest', 'io.github.ell.EarFun',
            '--object-path', '/io/github/ell/EarFun', '--method', 'io.github.ell.EarFun.' + method, *args],
            text=True, timeout=8)
        return json.loads(ast.literal_eval(output)[0])

    def test_get_state_and_invalid_request(self):
        state = self.call('GetState')
        self.assertTrue(state['connected'])
        self.assertEqual(state['name'], 'Test EarFun')
        self.assertFalse(self.call('Request', 'reset', '')['ok'])
        self.call('Request', 'status', '')

    def test_write_readback_and_unverified_eq_survive_dbus(self):
        result = self.call('Request', 'noise', 'anc')
        self.assertTrue(result['verified'])
        self.assertEqual(self.call('GetState')['values']['noise']['data']['value'], 'anc')
        result = self.call('Request', 'eq', 'bass')
        self.assertFalse(result['device_state_verified'])

    def test_main_loop_stays_responsive_and_rejects_overlapping_command(self):
        process = subprocess.Popen(['gdbus', 'call', '--session', '--dest', 'io.github.ell.EarFun',
            '--object-path', '/io/github/ell/EarFun', '--method', 'io.github.ell.EarFun.Request', 'noise', 'anc'],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 3
            while time.monotonic() < deadline:
                if self.call('GetState')['busy']:
                    break
            else:
                self.fail('Did not observe busy state')
            result = self.call('Request', 'game', 'on')
            self.assertFalse(result['ok'])
            stdout, stderr = process.communicate(timeout=5)
            self.assertEqual(process.returncode, 0, stderr)
            self.assertTrue(json.loads(ast.literal_eval(stdout)[0])['verified'])
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)

if __name__ == '__main__':
    unittest.main()
