#!/usr/bin/env python3
"""Session D-Bus service. Bluetooth work runs off the GLib main thread."""
import json
from pathlib import Path
import signal
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gi
from gi.repository import Gio, GLib
from earfun_cli.config import load_config
from service.backend import Backend, merge_result, new_state, request_args

BUS_NAME = 'io.github.ell.EarFun'
OBJECT_PATH = '/io/github/ell/EarFun'
INTERFACE = BUS_NAME
XML = '''<node><interface name="io.github.ell.EarFun">
<method name="GetState"><arg name="state" type="s" direction="out"/></method>
<method name="Request"><arg name="command" type="s" direction="in"/>
<arg name="value" type="s" direction="in"/><arg name="result" type="s" direction="out"/></method>
<signal name="StateChanged"><arg name="state" type="s"/></signal>
</interface></node>'''


class Service:
    def __init__(self, config):
        self.state = new_state(config)
        self.system = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
        self.backend = Backend(config, connection_check=self.device_info)
        self.connection = None
        self.loop = GLib.MainLoop()
        self.registration = None
        self.poll = 0
        self.failed = False
        self.refresh_pending = False
        suffix = '/dev_' + config['mac'].replace(':', '_')
        def device_changed(connection, sender, path, interface, signal_name, parameters):
            if path.endswith(suffix):
                _, changed, invalidated = parameters.unpack()
                if 'Connected' in changed or 'Connected' in invalidated:
                    if self.state['busy']:
                        self.refresh_pending = True
                    else:
                        self.start()
        self.bluez_signal = self.system.signal_subscribe('org.bluez', 'org.freedesktop.DBus.Properties',
            'PropertiesChanged', None, 'org.bluez.Device1', Gio.DBusSignalFlags.NONE, device_changed)

    def device_info(self):
        # Resolve adapter dynamically; never assume hci0.
        reply = self.system.call_sync('org.bluez', '/', 'org.freedesktop.DBus.ObjectManager',
            'GetManagedObjects', None, GLib.VariantType.new('(a{oa{sa{sv}}})'),
            Gio.DBusCallFlags.NONE, 3000, None).unpack()[0]
        for interfaces in reply.values():
            props = interfaces.get('org.bluez.Device1', {})
            if props.get('Address', '').upper() == self.backend.config['mac'].upper():
                return {'connected': props.get('Connected', False),
                        'name': props.get('Alias', props.get('Name', 'EarFun Air Pro 4i'))}
        return {'connected': False, 'name': self.state['name']}

    def publish(self):
        if self.connection:
            self.connection.emit_signal(None, OBJECT_PATH, INTERFACE, 'StateChanged',
                GLib.Variant('(s)', (json.dumps(self.state),)))

    def call(self, connection, sender, path, interface, method, parameters, invocation):
        if method == 'GetState':
            invocation.return_value(GLib.Variant('(s)', (json.dumps(self.state),)))
        elif method == 'Request':
            command, value = parameters.unpack()
            self.start(command, value, invocation)
        else:
            invocation.return_dbus_error(INTERFACE + '.UnknownMethod', 'Unknown method')

    def start(self, command='status', value='', invocation=None):
        try:
            request_args(self.backend.config, command, value)
        except ValueError as error:
            if invocation:
                invocation.return_value(GLib.Variant('(s)', (json.dumps(
                    {'ok': False, 'error': str(error)}),)))
            return GLib.SOURCE_CONTINUE
        if self.state['busy']:
            if invocation:
                invocation.return_value(GLib.Variant('(s)', (json.dumps(
                    {'ok': False, 'error': 'Perintah lain masih berjalan'}),)))
            return GLib.SOURCE_CONTINUE
        self.state['busy'] = True
        self.publish()
        def worker():
            try:
                result = self.backend.request(command, value)
            except Exception as error:
                # BlueZ/config failure: clear old values instead of presenting live data.
                result = {'ok': False, 'error': str(error),
                          'connection_check_failed': True,
                          'device_info': {'connected': False, 'name': self.state['name']}}
            GLib.idle_add(self.finish, command, result, invocation)
        threading.Thread(target=worker, daemon=True).start()
        return GLib.SOURCE_CONTINUE

    def finish(self, command, result, invocation):
        self.state = merge_result(self.state, command, result, time.time())
        self.publish()
        if invocation:
            invocation.return_value(GLib.Variant('(s)', (json.dumps(result),)))
        if self.refresh_pending:
            self.refresh_pending = False
            self.start()
        return GLib.SOURCE_REMOVE

    def acquired(self, connection, name):
        self.connection = connection
        info = Gio.DBusNodeInfo.new_for_xml(XML)
        self.registration = connection.register_object(OBJECT_PATH, info.interfaces[0], self.call, None, None)

    def ready(self, connection, name):
        self.start()
        self.poll = GLib.timeout_add_seconds(30, self.start)

    def lost(self, connection, name):
        print('EarFun D-Bus name unavailable', file=sys.stderr)
        self.failed = True
        self.loop.quit()

    def run(self):
        owner = Gio.bus_own_name(Gio.BusType.SESSION, BUS_NAME, Gio.BusNameOwnerFlags.NONE,
            self.acquired, self.ready, self.lost)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.loop.quit)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.loop.quit)
        try:
            self.loop.run()
        finally:
            if self.poll:
                GLib.source_remove(self.poll)
            if self.connection and self.registration:
                self.connection.unregister_object(self.registration)
            Gio.bus_unown_name(owner)
            self.system.signal_unsubscribe(self.bluez_signal)
        return 1 if self.failed else 0


if __name__ == '__main__':
    config = load_config()
    if not config:
        sys.exit('Run earfunctl.py configure --mac MAC --channel CHANNEL first')
    sys.exit(Service(config).run())
