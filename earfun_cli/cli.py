import argparse
import json
import math
import shutil
import socket
import sys

from . import __version__
from .config import PRESETS, load_config, save_config
from .protocol import BATTERY, CASE_BATTERY, FEATURES, FREQUENCIES, GAINS, VERSION, Frame, FrameStream, ProtocolError, decode_value, eq_frames
from .transport import Trace, TransportError, connect, device_list, discover, validate_mac


class OperationError(RuntimeError):
    def __init__(self, message, details):
        super().__init__(message)
        self.details = details


def positive_seconds(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Timeout must be a finite positive number")
    return number


def parser():
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--mac", type=validate_mac, default=argparse.SUPPRESS)
    common.add_argument("--channel", type=int, choices=range(1, 31), metavar="1..30", default=argparse.SUPPRESS)
    common.add_argument("--timeout", type=positive_seconds, default=argparse.SUPPRESS)
    common.add_argument("--json", action="store_true", default=argparse.SUPPRESS)
    common.add_argument("--trace", metavar="FILE.jsonl", default=argparse.SUPPRESS)
    common.add_argument("--dry-run", action="store_true", default=argparse.SUPPRESS)
    root = argparse.ArgumentParser(prog="earfunctl", parents=[common], description="Experimental Air Pro 4i controller. Run 'doctor' and 'status' first.")
    root.add_argument("--version", action="version", version="earfunctl " + __version__)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("doctor", "devices", "discover", "version", "battery", "configure"):
        commands.add_parser(name, parents=[common])
    status = commands.add_parser("status", parents=[common])
    status.add_argument("--full", action="store_true", help="Also query ANC level, spatial audio, multipoint")
    for name, feature in FEATURES.items():
        feature_parser = commands.add_parser(name, parents=[common])
        feature_parser.add_argument("value", nargs="?", default="get", choices=["get", *feature.values])
    eq = commands.add_parser("eq", parents=[common], description="Write 10-band EQ; current EQ readback is not implemented.")
    group = eq.add_mutually_exclusive_group(required=True)
    group.add_argument("--preset", choices=list(PRESETS))
    group.add_argument("--gains", metavar="DB,DB,...", help="10 gains in frequency order. Supported: " + str(list(GAINS)))
    decode = commands.add_parser("decode", parents=[common])
    decode.add_argument("hex", help="One or more complete captured EF...FE packets")
    return root


def read_plan(args):
    name = args.command
    if name == "version":
        return [("version", VERSION)]
    if name == "battery":
        return [("earbuds", BATTERY), ("case", CASE_BATTERY)]
    if name == "status":
        values = [("version", VERSION), ("earbuds", BATTERY), ("case", CASE_BATTERY), ("noise", FEATURES["noise"].get_opcode), ("game", FEATURES["game"].get_opcode)]
        if args.full:
            values.extend((name, FEATURES[name].get_opcode) for name in ("anc-level", "spatial", "multipoint"))
        return values
    if name in FEATURES:
        return [(name, FEATURES[name].get_opcode)]
    return []


def eq_gains(args):
    try:
        return list(PRESETS[args.preset]) if args.preset else [float(s.strip()) for s in args.gains.split(",")]
    except ValueError as error:
        raise ProtocolError("Gains must be comma-separated numbers") from error


def request_frames(args):
    if args.command == "eq":
        return eq_frames(eq_gains(args))
    frames = []
    if args.command in FEATURES and args.value != "get":
        frames.append(FEATURES[args.command].setting(args.value))
    frames.extend(Frame(opcode, b"") for _, opcode in read_plan(args))
    return frames


def dry_run(args):
    if args.command in ("doctor", "devices", "discover", "decode"):
        raise ValueError("Dry-run is for commands that send protocol packets")
    frames = request_frames(args)
    return {"ok": True, "dry_run": True, "command": args.command, "frames": [f.as_dict() for f in frames], "hardware_tested": False}


def query_values(session, queries):
    values, errors = {}, {}
    for name, opcode in queries:
        try:
            frame = session.query(opcode)
            values[name] = {"data": decode_value(frame), "response_hex": frame.encode().hex()}
        except (TransportError, OSError, UnicodeError, ProtocolError) as error:
            errors[name] = str(error)
    return {"ok": not errors, "status": "partial" if errors else "complete", "values": values, "errors": errors}


def set_feature(session, name, value):
    feature = FEATURES[name]
    sent = False
    try:
        session.send(feature.setting(value))
        sent = True
        observed = feature.decode(session.query(feature.get_opcode))
    except (OSError, TransportError, ProtocolError, KeyboardInterrupt) as error:
        raise OperationError("Feature write/readback did not complete: " + str(error), {"command": name, "requested": value, "transport_sent": sent, "delivery_uncertain": not sent, "verified": False}) from error
    verified = observed["value"] == value
    return {"ok": verified, "command": name, "requested": value, "observed": observed, "transport_sent": True, "verified": verified}


def set_eq(session, gains):
    frames = eq_frames(gains)
    completed = 0
    try:
        for frame in frames:
            session.send(frame)
            completed += 1
    except (OSError, TransportError, KeyboardInterrupt) as error:
        raise OperationError("EQ write interrupted; device may contain a partial change", {"command": "eq", "bands_transport_sent": completed, "total_bands": 10, "next_band_delivery_uncertain": completed + 1, "device_state_verified": False}) from error
    return {"ok": True, "command": "eq", "status": "transport_sent_unverified", "bands_transport_sent": completed, "gains_db": gains, "frequencies_hz": FREQUENCIES, "device_state_verified": False, "note": "All 10 frames were sent. Device acceptance, audible effect and persistence need hardware validation."}


def execute(args):
    if args.command == "configure":
        if not hasattr(args, "mac") or not hasattr(args, "channel"):
            raise ValueError("configure requires --mac and a discovered --channel")
        if getattr(args, "dry_run", False):
            from .config import validate_config
            return {"ok": True, "dry_run": True, "default_device": validate_config({"mac": args.mac, "channel": args.channel})}
        return {"ok": True, "default_device": save_config(args.mac, args.channel)}
    if getattr(args, "dry_run", False):
        return dry_run(args)
    if args.command == "doctor":
        live = sys.platform == "linux" and hasattr(socket, "AF_BLUETOOTH") and hasattr(socket, "BTPROTO_RFCOMM")
        return {"ok": live, "version": __version__, "platform": sys.platform, "python": sys.version.split()[0], "rfcomm_python_support": live, "bluetoothctl": shutil.which("bluetoothctl"), "sdptool": shutil.which("sdptool"), "adapter_or_device_tested": False}
    if args.command == "devices":
        return {"ok": True, "devices": device_list()}
    if args.command == "decode":
        stream = FrameStream()
        frames = stream.feed(bytes.fromhex(args.hex))
        if not frames or stream.buffer or stream.invalid_frames or stream.discarded_bytes:
            raise ProtocolError("Input must contain only complete valid packets")
        result = []
        for frame in frames:
            record = frame.as_dict()
            try:
                record["decoded"] = decode_value(frame)
            except (ProtocolError, UnicodeError):
                record["decoded"] = None
            result.append(record)
        return {"ok": True, "frames": result}
    mac = getattr(args, "mac", None)
    if mac is None:
        raise ValueError("Provide --mac from 'devices'; no device is selected automatically")
    if args.command == "discover":
        return {"ok": True, **discover(mac)}
    # Validate every EQ frame before opening a connection or changing anything.
    gains = eq_gains(args) if args.command == "eq" else None
    if gains is not None:
        eq_frames(gains)
    channel = getattr(args, "channel", None)
    if channel is None:
        channels = discover(mac)["channels"]
        if len(channels) != 1:
            raise TransportError(f"SPP discovery found channels {channels}; choose a known channel with --channel")
        channel = channels[0]
    trace = Trace(getattr(args, "trace", None))
    session = None
    try:
        session = connect(mac, channel, getattr(args, "timeout", 3.0), trace)
        if gains is not None:
            result = set_eq(session, gains)
        elif args.command in FEATURES and args.value != "get":
            result = set_feature(session, args.command, args.value)
        else:
            result = query_values(session, read_plan(args))
        return {"command": args.command, "device": mac, "channel": channel, **result}
    finally:
        try:
            if session is not None:
                session.close()
        finally:
            trace.close()


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command not in ("doctor", "devices", "decode", "configure"):
            defaults = load_config()
            # An explicit different MAC must never inherit another device's channel.
            if not hasattr(args, "mac"):
                if "mac" in defaults:
                    args.mac = defaults["mac"]
                    if not hasattr(args, "channel"):
                        args.channel = defaults["channel"]
            elif args.mac == defaults.get("mac") and not hasattr(args, "channel"):
                args.channel = defaults["channel"]
        result = execute(args)
    except OperationError as error:
        result = {"ok": False, "error": str(error), **error.details}
    except (ValueError, OSError, TransportError) as error:
        result = {"ok": False, "error": str(error)}
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for key, value in result.items():
            print(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list, tuple)) else value}")
    return 0 if result.get("ok") else 2
