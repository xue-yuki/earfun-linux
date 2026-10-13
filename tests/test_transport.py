import socket
import threading
import unittest

from earfun_cli.protocol import BATTERY, VERSION, Frame
from earfun_cli.transport import TransportError, WireSession, parse_sdp, validate_mac

SPP = '''<record><attribute id="0x0001"><sequence><uuid value="0x1101"/></sequence></attribute>
<attribute id="0x0004"><sequence><sequence><uuid value="0x0100"/></sequence>
<sequence><uuid value="0x0003"/><uint8 value="0x02"/></sequence></sequence></attribute></record>'''


class DiscoveryTests(unittest.TestCase):
    def test_spp_service_and_channel(self):
        self.assertEqual(parse_sdp("Browsing...\n<?xml version='1.0'?>\n" + SPP), [2])

    def test_multiple_spp_records_are_not_silently_selected(self):
        self.assertEqual(parse_sdp(SPP + SPP.replace('value="0x02"', 'value="0x03"')), [2, 3])

    def test_different_service_cannot_supply_spp_channel(self):
        self.assertEqual(parse_sdp(SPP.replace("0x1101", "0x1108")), [])

    def test_full_uuid(self):
        self.assertEqual(parse_sdp(SPP.replace("0x1101", "00001101-0000-1000-8000-00805f9b34fb")), [2])

    def test_invalid_channel_or_xml(self):
        for xml in ("No service available", SPP.replace("0x02", "0x00"), SPP.replace("0x02", "0x20"), SPP.replace("uint8", "uint16")):
            with self.subTest(xml=xml), self.assertRaises(TransportError):
                parse_sdp(xml)

    def test_mac_is_validated_before_shell_or_socket_use(self):
        self.assertEqual(validate_mac("aa:bb:cc:dd:ee:ff"), "AA:BB:CC:DD:EE:FF")
        for value in ("localhost", "AA:BB", "AA:BB:CC:DD:EE:FF;echo bad"):
            with self.assertRaises(ValueError):
                validate_mac(value)


class StreamSocketTests(unittest.TestCase):
    def exchange(self, response_chunks):
        client, peer = socket.socketpair()
        peer.settimeout(1)
        errors = []
        def server():
            try:
                request = bytearray()
                while len(request) < 6:
                    part = peer.recv(6 - len(request))
                    if not part:
                        raise AssertionError("Client closed before request")
                    request.extend(part)
                self.assertEqual(bytes(request), bytes.fromhex("ef10140000fe"))
                for chunk in response_chunks:
                    peer.sendall(chunk)
            except BaseException as error:
                errors.append(error)
            finally:
                peer.close()
        worker = threading.Thread(target=server, daemon=True)
        worker.start()
        session = WireSession(client, timeout=0.5)
        try:
            response = session.query(BATTERY)
        finally:
            session.close()
            worker.join(2)
        self.assertFalse(worker.is_alive())
        if errors:
            raise errors[0]
        return response

    def test_real_stream_handles_fragmented_response(self):
        response = Frame(BATTERY, b"\x50\x46")
        wire = response.encode()
        self.assertEqual(self.exchange([wire[:2], wire[2:5], wire[5:]]), response)

    def test_real_stream_skips_unrelated_ack_and_bad_checksum(self):
        unrelated = Frame(VERSION, b"TW230").encode()
        response = Frame(BATTERY, b"\x50\x46")
        broken = bytearray(response.encode()); broken[-2] = 0
        self.assertEqual(self.exchange([unrelated + broken + response.encode()]), response)

    def test_socket_eof_is_failure(self):
        client, peer = socket.socketpair(); peer.close()
        session = WireSession(client, timeout=0.1)
        try:
            with self.assertRaises((TransportError, OSError)):
                session.query(BATTERY)
        finally:
            session.close()

    def test_socket_timeout_is_failure(self):
        client, peer = socket.socketpair()
        session = WireSession(client, timeout=0.02)
        try:
            with self.assertRaises(TransportError):
                session.query(BATTERY)
        finally:
            session.close(); peer.close()
