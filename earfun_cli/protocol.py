"""TW230 packet semantics. No Bluetooth, filesystem, or UI effects."""
from dataclasses import dataclass
import math
import struct

SPP_UUID = "00001101-0000-1000-8000-00805f9b34fb"
VERSION = bytes.fromhex("1010")
BATTERY = bytes.fromhex("1014")
CASE_BATTERY = bytes.fromhex("1018")
SET_EQ = bytes.fromhex("2095")
FREQUENCIES = (31.5, 63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000)
GAINS = (-6, -5, -4, -3.5, -3, -2.5, -2, -1.5, -1, -0.5,
         0, 0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 5, 6)
MASTER_GAINS = (-11,) * 17 + (-11.5, -12, -13, -14)


class ProtocolError(ValueError):
    pass


@dataclass(frozen=True)
class Frame:
    opcode: bytes
    payload: bytes

    def encode(self):
        if len(self.opcode) != 2 or len(self.payload) > 255:
            raise ProtocolError("Opcode must have 2 bytes; payload at most 255 bytes")
        checksum = (len(self.payload) + sum(self.payload)) & 255
        return b"\xef" + self.opcode + bytes([len(self.payload)]) + self.payload + bytes([checksum, 0xFE])

    @classmethod
    def decode(cls, data):
        if len(data) < 6 or data[0] != 0xEF or len(data) != data[3] + 6:
            raise ProtocolError("Incomplete or invalid frame length")
        if data[-1] != 0xFE:
            raise ProtocolError("Invalid frame terminator")
        payload = bytes(data[4:-2])
        if data[-2] != (len(payload) + sum(payload)) & 255:
            raise ProtocolError("Invalid checksum")
        return cls(bytes(data[1:3]), payload)

    def as_dict(self):
        return {"opcode": self.opcode.hex(), "payload": self.payload.hex(), "frame": self.encode().hex()}


class FrameStream:
    """Length-based framing, including EF/FE bytes inside payloads."""
    def __init__(self):
        self.buffer = bytearray()
        self.discarded_bytes = 0
        self.invalid_frames = 0

    def feed(self, data):
        self.buffer.extend(data)
        frames = []
        while self.buffer:
            start = self.buffer.find(b"\xef")
            if start < 0:
                self.discarded_bytes += len(self.buffer)
                self.buffer.clear()
                break
            if start:
                self.discarded_bytes += start
                del self.buffer[:start]
            if len(self.buffer) < 4:
                break
            size = self.buffer[3] + 6
            if len(self.buffer) < size:
                break
            try:
                frame = Frame.decode(bytes(self.buffer[:size]))
            except ProtocolError:
                self.invalid_frames += 1
                self.discarded_bytes += 1
                del self.buffer[0]
                continue
            frames.append(frame)
            del self.buffer[:size]
        return frames


@dataclass(frozen=True)
class Feature:
    get_opcode: bytes
    set_opcode: bytes
    values: dict

    def setting(self, name):
        return Frame(self.set_opcode, bytes([self.values[name]]))

    def decode(self, frame):
        if frame.opcode != self.get_opcode or len(frame.payload) != 1:
            raise ProtocolError("Expected a one-byte feature response")
        raw = frame.payload[0]
        name = next((k for k, v in self.values.items() if v == raw), None)
        return {"value": name, "raw_value": raw, "known": name is not None}


FEATURES = {
    "noise": Feature(bytes.fromhex("2080"), bytes.fromhex("2085"), {"normal": 1, "ambient": 2, "anc": 3}),
    "game": Feature(bytes.fromhex("2030"), bytes.fromhex("2035"), {"off": 1, "on": 2}),
    "anc-level": Feature(bytes.fromhex("2310"), bytes.fromhex("2315"), {"strong": 1, "balanced": 2, "wind": 3, "adaptive": 4}),
    "spatial": Feature(bytes.fromhex("2190"), bytes.fromhex("2195"), {"off": 1, "on": 2}),
    "multipoint": Feature(bytes.fromhex("2140"), bytes.fromhex("2145"), {"off": 1, "on": 2}),
}


def battery_value(raw):
    return {"percent": raw if raw <= 100 else None, "raw_value": raw, "known": raw <= 100}


def decode_value(frame):
    if frame.opcode == VERSION:
        text = frame.payload.replace(b"\x00", b"").decode("utf-8")
        if not text:
            raise ProtocolError("Empty firmware version")
        return {"firmware": text, "model_hint": "TW230" if "TW230" in text.upper() else None}
    if frame.opcode == BATTERY:
        if len(frame.payload) != 2:
            raise ProtocolError("Expected two battery bytes")
        return {"left": battery_value(frame.payload[0]), "right": battery_value(frame.payload[1])}
    if frame.opcode == CASE_BATTERY:
        if len(frame.payload) != 1:
            raise ProtocolError("Expected one case battery byte")
        return battery_value(frame.payload[0])
    for feature in FEATURES.values():
        if frame.opcode == feature.get_opcode:
            return feature.decode(frame)
    raise ProtocolError("No value decoder for opcode " + frame.opcode.hex())


def eq_frames(gains):
    """Match TW230Equailzer.sendEq: slider lookup, per-band master headroom."""
    if len(gains) != 10:
        raise ProtocolError("EQ requires exactly 10 gain values")
    indices = []
    for gain in gains:
        if not math.isfinite(gain) or gain not in GAINS:
            raise ProtocolError("Unsupported gain; use values from " + str(list(GAINS)))
        indices.append(GAINS.index(gain))
    master = MASTER_GAINS[max(indices)]
    frames = []
    for index, (frequency, gain) in enumerate(zip(FREQUENCIES, gains), 1):
        payload = bytes([10, index]) + struct.pack(">hHhH", int(master * 60), int(frequency * 3), int(gain * 60), 2867)
        frames.append(Frame(SET_EQ, payload))
    return frames
