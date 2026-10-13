"""Linux RFCOMM and explicit SPP service discovery."""
import json
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
import xml.etree.ElementTree as ET

from .protocol import Frame, FrameStream, SPP_UUID


class TransportError(RuntimeError):
    pass


def validate_mac(value):
    if not re.fullmatch(r"(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}", value):
        raise ValueError("MAC must look like AA:BB:CC:DD:EE:FF")
    return value.upper()


def command_output(arguments, timeout=12):
    if shutil.which(arguments[0]) is None:
        raise TransportError(f"{arguments[0]} is unavailable; install the corresponding BlueZ utility")
    try:
        result = subprocess.run(arguments, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        raise TransportError(f"{arguments[0]} timed out") from error
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise TransportError(f"{arguments[0]}: {detail}")
    return result.stdout


def device_list():
    text = command_output(["bluetoothctl", "devices"])
    devices = []
    for line in text.splitlines():
        match = re.fullmatch(r"Device ((?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}) (.+)", line.strip())
        if match:
            devices.append({"mac": match[1].upper(), "name": match[2]})
    return devices


def _is_uuid(value, short):
    value = value.lower()
    return value in ("0x" + short, short, "0000" + short + "-0000-1000-8000-00805f9b34fb")


def parse_sdp(text):
    """Select channel only from an SPP record, never a different profile."""
    records = re.findall(r"<record(?:\s[^>]*)?>.*?</record>", text, re.S)
    if not records:
        raise TransportError("No SDP XML records found")
    channels = set()
    for raw in records:
        try:
            record = ET.fromstring(raw)
            attrs = {int(a.attrib["id"], 0): a for a in record.findall("attribute")}
            service = attrs.get(1)
            if service is None or not any(_is_uuid(n.attrib.get("value", ""), "1101") for n in service.iter("uuid")):
                continue
            protocols = attrs.get(4)
            if protocols is None:
                continue
            for seq in protocols.iter("sequence"):
                children = list(seq)
                if not children or children[0].tag != "uuid" or not _is_uuid(children[0].attrib.get("value", ""), "0003"):
                    continue
                if len(children) < 2 or children[1].tag != "uint8":
                    raise ValueError("Missing RFCOMM uint8 channel")
                channel = int(children[1].attrib["value"], 0)
                if not 1 <= channel <= 30:
                    raise ValueError("RFCOMM channel outside 1..30")
                channels.add(channel)
        except (ValueError, KeyError, ET.ParseError) as error:
            raise TransportError(f"Malformed SDP record: {error}") from error
    return sorted(channels)


def discover(mac):
    mac = validate_mac(mac)
    channels = parse_sdp(command_output(["sdptool", "browse", "--xml", mac]))
    return {"mac": mac, "service_uuid": SPP_UUID, "channels": channels}


class Trace:
    def __init__(self, path=None):
        self.file = Path(path).open("a", encoding="utf-8") if path else None

    def write(self, event, **values):
        if self.file:
            record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **values}
            self.file.write(json.dumps(record, ensure_ascii=False) + "\n")
            self.file.flush()

    def close(self):
        if self.file:
            self.file.close()


class WireSession:
    """A sequential request/response session over a connected stream socket."""
    def __init__(self, sock, timeout=3.0, trace=None):
        self.sock = sock
        self.timeout = timeout
        self.trace = trace or Trace()
        self.decoder = FrameStream()
        self.last_send = None

    def send(self, frame):
        if self.last_send is not None:
            remaining = 0.05 - (time.monotonic() - self.last_send)
            if remaining > 0:
                time.sleep(remaining)
        self.sock.settimeout(self.timeout)
        data = frame.encode()
        self.trace.write("tx_attempt", frame=data.hex())
        self.sock.sendall(data)
        self.last_send = time.monotonic()
        self.trace.write("tx_complete", frame=data.hex())

    def query(self, opcode):
        self.send(Frame(opcode, b""))
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TransportError(f"No matching response for {opcode.hex()}")
            self.sock.settimeout(remaining)
            try:
                data = self.sock.recv(4096)
            except socket.timeout as error:
                raise TransportError(f"Response timeout for {opcode.hex()}") from error
            if not data:
                raise TransportError("Device closed the control connection")
            self.trace.write("rx_chunk", data=data.hex())
            frames = self.decoder.feed(data)
            match = None
            for frame in frames:
                self.trace.write("rx_frame", **frame.as_dict())
                if match is None and frame.opcode == opcode:
                    match = frame
            if match is not None:
                return match

    def close(self):
        self.sock.close()


def connect(mac, channel, timeout, trace):
    if sys.platform != "linux" or not hasattr(socket, "AF_BLUETOOTH") or not hasattr(socket, "BTPROTO_RFCOMM"):
        raise TransportError("Live control requires Linux Python with RFCOMM support; dry-run works offline")
    mac = validate_mac(mac)
    if not 1 <= channel <= 30:
        raise ValueError("RFCOMM channel must be 1..30")
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    try:
        sock.settimeout(timeout)
        sock.connect((mac, channel))
        trace.write("connected", mac=mac, channel=channel)
        return WireSession(sock, timeout, trace)
    except BaseException:
        sock.close()
        raise
