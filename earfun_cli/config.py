"""Per-user device configuration; no automatic Bluetooth writes."""
import json
import os
from pathlib import Path
import tempfile

from .transport import validate_mac

PRESETS = {
    "flat": [0] * 10,
    "bass": [3, 3, 2, 1, 0, 0, 0, 0, 0, 0],
    "vocal": [0, 0, -1, -1, 1, 2, 2, 1, 0, 0],
}


def config_path():
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "earfun" / "config.json"


def validate_config(data):
    if not isinstance(data, dict) or "mac" not in data or "channel" not in data:
        raise ValueError("Invalid EarFun config: expected mac and channel")
    if not isinstance(data["mac"], str):
        raise ValueError("Configured MAC must be a string")
    mac = validate_mac(data["mac"])
    channel = data["channel"]
    if type(channel) is not int or not 1 <= channel <= 30:
        raise ValueError("Channel must be an integer from 1 to 30, confirmed by discovery")
    return {"mac": mac, "channel": channel}


def load_config():
    try:
        return validate_config(json.loads(config_path().read_text()))
    except FileNotFoundError:
        return {}


def save_config(mac, channel):
    data = validate_config({"mac": mac, "channel": channel})
    path = config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".config-")
    try:
        with os.fdopen(fd, "w") as handle:
            json.dump(data, handle, indent=2)
            handle.write("\n")
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return data
