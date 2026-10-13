#!/usr/bin/env python3
"""Install only under the current user's directories; never needs sudo."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from earfun_cli.config import save_config, validate_config

UUID = 'earfun@ell.local'
ROOT = Path(__file__).resolve().parent


def unit_text(service_path):
    # systemd quoted argument escaping, including literal % specifiers.
    escaped = str(service_path).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%').replace('$', '$$')
    if '\n' in escaped or '\r' in escaped:
        raise ValueError('Install path must not contain newlines')
    return f'''[Unit]
Description=EarFun Air Pro 4i local controller
After=bluetooth.target
StartLimitIntervalSec=0

[Service]
Type=dbus
BusName=io.github.ell.EarFun
ExecStart=/usr/bin/python3 "{escaped}"
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mac', required=True)
    parser.add_argument('--channel', required=True, type=int)
    parser.add_argument('--dry-run', action='store_true', help='Validate paths/config without copying or starting anything')
    args = parser.parse_args()
    config = validate_config({'mac': args.mac, 'channel': args.channel})
    if hasattr(os, 'geteuid') and os.geteuid() == 0 and not args.dry_run:
        sys.exit('Run as your normal user, without sudo')
    data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
    target = data / 'earfun-panel'
    extension = data / 'gnome-shell/extensions' / UUID
    unit = Path.home() / '.config/systemd/user/earfun.service'
    unit_data = unit_text(target / 'service/earfund.py')
    if args.dry_run:
        print(json.dumps({'config': config, 'app': str(target), 'extension': str(extension), 'unit': str(unit)}, indent=2))
        return
    for executable in ('systemctl', 'gnome-extensions', 'bluetoothctl'):
        if not shutil.which(executable):
            sys.exit(f'Missing dependency: {executable}')
    subprocess.run(['/usr/bin/python3', '-c', 'from gi.repository import Gio, GLib'], check=True)
    version = subprocess.check_output(['gnome-shell', '--version'], text=True).strip()
    if not version.split()[-1].startswith('50.') and version.split()[-1] != '50':
        sys.exit('This build targets GNOME Shell 50: ' + version)
    # Stop our installed service before replacing its files. Keep any other CLI project intact.
    subprocess.run(['systemctl', '--user', 'stop', 'earfun.service'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    target.mkdir(parents=True, exist_ok=True)
    for directory in ('earfun_cli', 'service'):
        shutil.copytree(ROOT / directory, target / directory, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    shutil.copy2(ROOT / 'earfunctl.py', target / 'earfunctl.py')
    shutil.copytree(ROOT / 'extension' / UUID, extension, dirs_exist_ok=True)
    save_config(**config)
    unit.parent.mkdir(parents=True, exist_ok=True)
    unit.write_text(unit_data)
    # Custom XDG_CONFIG_HOME must also reach the daemon, not just this installer.
    config_root = Path(os.environ.get('XDG_CONFIG_HOME', Path.home() / '.config'))
    dropin = unit.parent / 'earfun.service.d/config.conf'
    dropin.parent.mkdir(parents=True, exist_ok=True)
    environment = str(config_root).replace('\\', '\\\\').replace('"', '\\"').replace('%', '%%')
    if '\n' in environment or '\r' in environment:
        sys.exit('Config path must not contain newlines')
    dropin.write_text(f'[Service]\nEnvironment="XDG_CONFIG_HOME={environment}"\n')
    subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', '--user', 'enable', '--now', 'earfun.service'], check=True)
    result = subprocess.run(['gnome-extensions', 'enable', UUID], capture_output=True, text=True)
    print('Service installed. Extension: ' + UUID)
    if result.returncode:
        print('GNOME may not have discovered the new extension yet. Log out and log in, then run:')
        print('gnome-extensions enable ' + UUID)
    else:
        print('Extension enabled. If updating a loaded version, log out and log in to reload its JavaScript.')
    print('Service logs: journalctl --user -u earfun.service -n 40 --no-pager')


if __name__ == '__main__':
    main()
