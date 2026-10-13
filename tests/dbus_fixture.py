"""Test-only fake device behind the real Gio service; no Bluetooth access."""
from pathlib import Path
import sys
import time
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from gi.repository import Gio, GLib
from service.earfund import Service

bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
with patch('service.earfund.Gio.bus_get_sync', return_value=bus):
    service = Service({'mac': '02:00:00:00:00:01', 'channel': 1})
service.backend.connection_check = lambda: {'connected': True, 'name': 'Test EarFun'}

def runner(args):
    if args.command == 'noise':
        time.sleep(0.35)
        return {'ok': True, 'command': 'noise', 'verified': True,
                'observed': {'known': True, 'value': args.value, 'raw_value': 3}}
    if args.command == 'eq':
        return {'ok': True, 'command': 'eq', 'device_state_verified': False,
                'bands_transport_sent': 10}
    return {'ok': True, 'command': 'status', 'values': {}, 'errors': {}}

service.backend.runner = runner
original = service.ready

def ready(connection, name):
    original(connection, name)
    print('READY', flush=True)

service.ready = ready
service.run()
