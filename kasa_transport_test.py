"""Unit tests for kasa_transport shared framed TCP protocol."""

import json
import struct
import unittest
from unittest import mock

import kasa_transport as kt


class FakeSocket:
  def __init__(self, chunks):
    self._chunks = list(chunks)
    self.sent = bytearray()

  def sendall(self, data):
    self.sent.extend(data)

  def recv(self, n):
    if not self._chunks:
      return b''
    chunk = self._chunks.pop(0)
    if len(chunk) > n:
      self._chunks.insert(0, chunk[n:])
      return chunk[:n]
    return chunk


class KasaTransportTests(unittest.TestCase):
  def test_encrypt_decrypt_roundtrip(self):
    payload = '{"system":{"set_relay_state":{"state":1}}}'
    framed = kt.encrypt(payload)
    (length,) = struct.unpack('>I', framed[:4])
    self.assertEqual(length, len(payload.encode('utf-8')))
    self.assertEqual(kt.decrypt(framed[4:]), payload)

  def test_recv_exact_handles_fragmented_reads(self):
    sock = FakeSocket([b'ab', b'c', b'def'])
    self.assertEqual(kt.recv_exact(sock, 6), b'abcdef')

  def test_recv_exact_raises_on_eof(self):
    sock = FakeSocket([b'ab'])
    with self.assertRaises(OSError):
      kt.recv_exact(sock, 4)

  def test_send_command_parses_fragmented_framed_json(self):
    resp_obj = {'system': {'set_relay_state': {'err_code': 0}}}
    framed_resp = kt.encrypt(json.dumps(resp_obj))
    # Split across header and body boundaries
    sock = FakeSocket([framed_resp[:2], framed_resp[2:7], framed_resp[7:]])
    req = kt.encrypt('{"system":{"set_relay_state":{"state":1}}}')
    parsed = kt.send_command(sock, req)
    self.assertEqual(parsed, resp_obj)
    self.assertEqual(bytes(sock.sent), req)

  def test_send_command_rejects_zero_or_oversized_length(self):
    for length in (0, kt.MAX_PAYLOAD_BYTES + 1):
      with self.subTest(length=length):
        sock = FakeSocket([struct.pack('>I', length)])
        with self.assertRaises(ValueError):
          kt.send_command(sock, b'\x00\x00\x00\x02{}')

  def test_send_command_rejects_non_object_json(self):
    framed = kt.encrypt('[1, 2, 3]')
    sock = FakeSocket([framed])
    with self.assertRaises(ValueError):
      kt.send_command(sock, b'req')

  def test_check_ack_accepts_explicit_zero_err_code(self):
    resp = {'system': {'set_relay_state': {'err_code': 0, 'ok': True}}}
    res = kt.check_ack(resp, 'system', 'set_relay_state')
    self.assertEqual(res['err_code'], 0)

  def test_check_ack_rejects_missing_or_invalid_structures(self):
    cases = [
        ({}, ValueError),
        ({'system': 'bad'}, ValueError),
        ({'system': {}}, ValueError),
        ({'system': {'set_relay_state': {}}}, ValueError),
        ({'system': {'set_relay_state': {'err_code': -1}}}, RuntimeError),
        ({'system': {'set_relay_state': {'err_code': False}}}, RuntimeError),
        ({'system': {'set_relay_state': {'err_code': True}}}, RuntimeError),
    ]
    for resp, exc_type in cases:
      with self.subTest(resp=resp):
        with self.assertRaises(exc_type):
          kt.check_ack(resp, 'system', 'set_relay_state')


if __name__ == '__main__':
  unittest.main()
