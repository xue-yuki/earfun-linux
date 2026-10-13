import unittest

from earfun_cli.protocol import BATTERY, CASE_BATTERY, FEATURES, VERSION, Frame, FrameStream, ProtocolError, decode_value, eq_frames


class ProtocolTests(unittest.TestCase):
    def test_apk_derived_query_vectors(self):
        for opcode, expected in [(VERSION, "ef10100000fe"), (BATTERY, "ef10140000fe"), (CASE_BATTERY, "ef10180000fe")]:
            with self.subTest(opcode=opcode):
                self.assertEqual(Frame(opcode, b"").encode().hex(), expected)

    def test_apk_derived_write_vectors(self):
        cases = [("noise", "anc", "ef2085010304fe"), ("noise", "ambient", "ef2085010203fe"),
                 ("noise", "normal", "ef2085010102fe"), ("game", "on", "ef2035010203fe"),
                 ("anc-level", "adaptive", "ef2315010405fe"), ("spatial", "on", "ef2195010203fe"),
                 ("multipoint", "off", "ef2145010102fe")]
        for name, value, expected in cases:
            with self.subTest(name=name, value=value):
                self.assertEqual(FEATURES[name].setting(value).encode().hex(), expected)

    def test_signed_bytes_checksum_and_delimiters_in_payload(self):
        frame = Frame(bytes.fromhex("2095"), bytes.fromhex("effe80ff"))
        self.assertEqual(frame.encode().hex(), "ef209504effe80ff70fe")
        self.assertEqual(Frame.decode(frame.encode()), frame)

    def test_checksum_excludes_opcode(self):
        a = Frame(b"\x20\x85", b"\x03").encode()
        b = Frame(b"\x10\x14", b"\x03").encode()
        self.assertEqual(a[-2], b[-2])

    def test_stream_all_split_positions_and_coalesced_frames(self):
        first = Frame(BATTERY, b"\x50\x46")
        second = Frame(CASE_BATTERY, b"\x64")
        wire = first.encode() + second.encode()
        for cut in range(len(wire) + 1):
            with self.subTest(cut=cut):
                stream = FrameStream()
                self.assertEqual(stream.feed(wire[:cut]) + stream.feed(wire[cut:]), [first, second])
                self.assertEqual(stream.buffer, b"")

    def test_stream_resynchronizes_after_garbage_bad_checksum_and_bad_tail(self):
        valid = Frame(BATTERY, b"\x50\x46")
        broken = bytearray(valid.encode()); broken[-2] ^= 1
        bad_tail = bytearray(valid.encode()); bad_tail[-1] = 0
        stream = FrameStream()
        self.assertEqual(stream.feed(b"garbage" + broken + bad_tail + valid.encode()), [valid])
        self.assertEqual(stream.invalid_frames, 2)
        self.assertGreater(stream.discarded_bytes, 0)

    def test_reject_bad_length_checksum_or_tail(self):
        for wire in (b"", bytes.fromhex("ef10140000"), bytes.fromhex("ef10140001fe"), bytes.fromhex("ef1014000000")):
            with self.subTest(wire=wire), self.assertRaises(ProtocolError):
                Frame.decode(wire)

    def test_payload_capacity(self):
        self.assertEqual(len(Frame(VERSION, b"x" * 255).encode()), 261)
        with self.assertRaises(ProtocolError):
            Frame(VERSION, b"x" * 256).encode()

    def test_unknown_battery_is_not_reported_as_percent(self):
        value = decode_value(Frame(BATTERY, b"\x64\xff"))
        self.assertEqual(value["left"]["percent"], 100)
        self.assertIsNone(value["right"]["percent"])
        self.assertEqual(value["right"]["raw_value"], 255)

    def test_unknown_mode_is_not_defaulted_to_normal(self):
        value = FEATURES["noise"].decode(Frame(bytes.fromhex("2080"), b"\x7f"))
        self.assertFalse(value["known"])
        self.assertIsNone(value["value"])

    def test_malformed_battery_payload(self):
        with self.assertRaises(ProtocolError):
            decode_value(Frame(BATTERY, b"\x64"))

    def test_version_removes_null_padding(self):
        result = decode_value(Frame(VERSION, b"TW230_\x00v0.6.0\x00"))
        self.assertEqual(result["firmware"], "TW230_v0.6.0")
        self.assertEqual(result["model_hint"], "TW230")

    def test_flat_eq_golden_first_and_last_bands(self):
        frames = eq_frames([0] * 10)
        self.assertEqual(len(frames), 10)
        self.assertEqual(frames[0].encode().hex(), "ef20950a0a01fd6c005e00000b331afe")
        self.assertEqual(frames[-1].encode().hex(), "ef20950a0a0afd6cbb8000000b3300fe")

    def test_eq_gain_and_master_headroom_golden_vectors(self):
        self.assertEqual(eq_frames([6] * 10)[0].encode().hex(), "ef20950a0a01fcb8005e01680b33cefe")
        self.assertEqual(eq_frames([-6] * 10)[0].encode().hex(), "ef20950a0a01fd6c005efe980b33b0fe")

    def test_invalid_eq_never_builds_a_partial_sequence(self):
        for gains in ([0] * 9, [0] * 11, [0] * 9 + [4.5], [0] * 9 + [float("nan")], [0] * 9 + [float("inf")]):
            with self.subTest(gains=gains), self.assertRaises(ProtocolError):
                eq_frames(gains)


if __name__ == "__main__":
    unittest.main()
