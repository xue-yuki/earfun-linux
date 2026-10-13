"""Native GLib main-loop tests; fake device and bus connection, no radio access."""
import importlib.util
import json
import threading
import time
import unittest
from unittest.mock import Mock, patch

HAS_GI = importlib.util.find_spec('gi') is not None
if HAS_GI:
    from gi.repository import GLib
    from service.earfund import Service

CONFIG = {'mac': '02:00:00:00:00:01', 'channel': 1}

@unittest.skipUnless(HAS_GI, 'Needs system Python with Gio')
class NativeGLibTests(unittest.TestCase):
    def setUp(self):
        properties = {'Address': GLib.Variant('s', CONFIG['mac']),
                      'Connected': GLib.Variant('b', True), 'Alias': GLib.Variant('s', 'ElamgaPods')}
        self.bus = Mock()
        self.bus.call_sync.return_value = GLib.Variant('(a{oa{sa{sv}}})',
            ({'/org/bluez/hci7/dev_02_00_00_00_00_01': {'org.bluez.Device1': properties}},))
        with patch('service.earfund.Gio.bus_get_sync', return_value=self.bus):
            self.service = Service(CONFIG)
        self.service.connection = Mock()

    def finish(self, invocation):
        loop = GLib.MainLoop()
        expired = []
        def check():
            if invocation.return_value.called:
                loop.quit()
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        timer = GLib.timeout_add(5, check)
        def timeout():
            expired.append(True)
            loop.quit()
            return GLib.SOURCE_REMOVE
        deadline = GLib.timeout_add(3000, timeout)
        loop.run()
        if expired:
            GLib.source_remove(timer)
            self.fail('Worker did not finish')
        else:
            GLib.source_remove(deadline)
        return json.loads(invocation.return_value.call_args.args[0].unpack()[0])

    def test_native_variant_device_lookup_on_nondefault_adapter(self):
        self.assertEqual(self.service.device_info(), {'connected': True, 'name': 'ElamgaPods'})

    def test_worker_uses_native_mainloop_to_return_verified_result(self):
        worker_threads = []
        def runner(args):
            worker_threads.append(threading.get_ident())
            return {'ok': True, 'command': 'noise', 'verified': True,
                    'observed': {'known': True, 'value': 'anc', 'raw_value': 3}}
        self.service.backend.runner = runner
        invocation = Mock()
        self.service.start('noise', 'anc', invocation)
        self.assertTrue(self.finish(invocation)['verified'])
        self.assertNotEqual(worker_threads[0], threading.get_ident())
        self.assertFalse(self.service.state['busy'])
        self.assertEqual(self.service.state['name'], 'ElamgaPods')
        self.service.connection.emit_signal.assert_called()

    def test_busy_request_rejected_and_state_read_immediate(self):
        def runner(args):
            time.sleep(.1)
            return {'ok': True, 'command': 'status', 'values': {}, 'errors': {}}
        self.service.backend.runner = runner
        first, second, state_call = Mock(), Mock(), Mock()
        self.service.start('status', '', first)
        self.service.start('game', 'on', second)
        self.assertFalse(json.loads(second.return_value.call_args.args[0].unpack()[0])['ok'])
        self.service.call(None, None, None, None, 'GetState', GLib.Variant('()', ()), state_call)
        self.assertTrue(json.loads(state_call.return_value.call_args.args[0].unpack()[0])['busy'])
        self.assertTrue(self.finish(first)['ok'])

    def test_invalid_request_leaves_connection_state_intact(self):
        self.service.state['connected'] = True
        invocation = Mock()
        self.service.start('reset', '', invocation)
        self.assertFalse(json.loads(invocation.return_value.call_args.args[0].unpack()[0])['ok'])
        self.assertTrue(self.service.state['connected'])
        self.assertFalse(self.service.state['busy'])

    def test_bluez_connection_signal_refreshes_and_coalesces_while_busy(self):
        callback = self.bus.signal_subscribe.call_args.args[-1]
        parameters = GLib.Variant('(sa{sv}as)', ('org.bluez.Device1', {'Connected': GLib.Variant('b', True)}, []))
        with patch.object(self.service, 'start') as start:
            callback(None, None, '/org/bluez/hci7/dev_02_00_00_00_00_01', None, None, parameters)
            start.assert_called_once()
            self.service.state['busy'] = True
            callback(None, None, '/org/bluez/hci7/dev_02_00_00_00_00_01', None, None, parameters)
            self.assertTrue(self.service.refresh_pending)
            start.assert_called_once()

    def test_lost_bus_marks_failure_for_service_recovery(self):
        self.service.loop = Mock()
        self.service.lost(None, 'io.github.ell.EarFun')
        self.assertTrue(self.service.failed)
        self.service.loop.quit.assert_called_once()

if __name__ == '__main__':
    unittest.main()
