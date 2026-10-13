#!/usr/bin/env python3
"""Remove this extension and service; preserve user configuration."""
import os
from pathlib import Path
import shutil
import subprocess
import sys

if hasattr(os, 'geteuid') and os.geteuid() == 0:
    sys.exit('Run without sudo')
subprocess.run(['gnome-extensions', 'disable', 'earfun@ell.local'], check=False)
subprocess.run(['systemctl', '--user', 'disable', '--now', 'earfun.service'], check=False)
data = Path(os.environ.get('XDG_DATA_HOME', Path.home() / '.local/share'))
for path in (data / 'earfun-panel', data / 'gnome-shell/extensions/earfun@ell.local',
             Path.home() / '.config/systemd/user/earfun.service.d'):
    if path.exists():
        shutil.rmtree(path)
(Path.home() / '.config/systemd/user/earfun.service').unlink(missing_ok=True)
subprocess.run(['systemctl', '--user', 'daemon-reload'], check=True)
print('Removed. EarFun configuration preserved. Log out/in to unload cached extension code.')
