"""UI-independent operations. Transport remains the tested earfun_cli code."""
import argparse
from earfun_cli.cli import execute, OperationError
from earfun_cli.config import PRESETS, validate_config
from earfun_cli.protocol import FEATURES


def request_args(config, command, value):
    config = validate_config(config)
    args = argparse.Namespace(**config, command=command, timeout=2.0)
    if command == "status":
        if value:
            raise ValueError("status takes no value")
        args.full = True
    elif command in FEATURES:
        if value not in FEATURES[command].values:
            raise ValueError("Unknown feature value")
        args.value = value
    elif command == "eq":
        if value not in PRESETS:
            raise ValueError("Unknown EQ preset")
        args.preset, args.gains = value, None
    else:
        raise ValueError("Unsupported command")
    return args


class Backend:
    def __init__(self, config, runner=execute, connection_check=None):
        self.config = validate_config(config)
        self.runner = runner
        self.connection_check = connection_check

    def request(self, command, value):
        # Validate before checking connection or opening RFCOMM.
        args = request_args(self.config, command, value)
        device = self.connection_check() if self.connection_check else {"connected": True}
        if not device.get("connected"):
            return {"ok": False, "error": "EarFun tidak tersambung", "device": device}
        try:
            result = self.runner(args)
        except OperationError as error:
            result = {"ok": False, "error": str(error), **error.details}
        except (ValueError, OSError, RuntimeError) as error:
            result = {"ok": False, "error": str(error)}
        result["device_info"] = device
        return result


def new_state(config):
    return {"mac": config["mac"], "name": "EarFun Air Pro 4i", "connected": False,
            "busy": False, "values": {}, "error": "Menunggu pemeriksaan koneksi",
            "last_result": None, "updated_at": None, "connection_checked": False}


def merge_result(state, command, result, now):
    state = {**state, "busy": False, "last_result": result}
    device = result.get("device_info", result.get("device", {}))
    if isinstance(device, dict):
        if "connected" in device:
            state["connection_checked"] = not result.get("connection_check_failed", False)
        state["connected"] = device.get("connected", state["connected"])
        state["name"] = device.get("name", state["name"])
    if not state["connected"]:
        state["values"] = {}
    elif command == "status":
        # Replace, never retain a failed field from a previous successful read.
        state["values"] = result.get("values", {})
        state["updated_at"] = now
    elif command in FEATURES:
        values = dict(state["values"])
        if "observed" in result:
            values[command] = {"data": result["observed"]}
        else:
            values.pop(command, None)
        state["values"] = values
    errors = result.get("errors", {})
    state["error"] = result.get("error") or ("; ".join(f"{k}: {v}" for k, v in errors.items()) if errors else None)
    if not result.get("ok") and not state["error"]:
        state["error"] = "Perubahan belum terverifikasi"
    return state
