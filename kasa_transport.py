"""Shared bounded TCP transport for TP-Link Kasa smartplugs (port 9999)."""

import json
import socket
from struct import pack, unpack
from typing import Any, Dict

SMARTPLUG_PORT = 9999
MAX_PAYLOAD_BYTES = 65536


def encrypt(string: str) -> bytes:
  """Encrypts a JSON command string for TP-Link smartplug protocol."""
  raw = string.encode('utf-8')
  key = 171
  out = bytearray(pack('>I', len(raw)))
  for b in raw:
    a = key ^ b
    key = a
    out.append(a)
  return bytes(out)


def decrypt(data: bytes) -> str:
  """Decrypts a TP-Link smartplug payload (without 4-byte length prefix)."""
  key = 171
  out = bytearray()
  for b in data:
    a = key ^ b
    key = b
    out.append(a)
  return out.decode('utf-8')


def recv_exact(sock: socket.socket, n: int) -> bytes:
  """Reads exactly n bytes from a TCP socket or raises OSError."""
  buf = bytearray()
  while len(buf) < n:
    chunk = sock.recv(n - len(buf))
    if not chunk:
      raise OSError(f'Unexpected EOF after {len(buf)}/{n} bytes')
    buf.extend(chunk)
  return bytes(buf)


def send_command(
    sock: socket.socket,
    payload: bytes,
    max_response_bytes: int = MAX_PAYLOAD_BYTES,
) -> Dict[str, Any]:
  """Sends a framed command with sendall and reads/parses the framed JSON response."""
  sock.sendall(payload)
  header = recv_exact(sock, 4)
  (length,) = unpack('>I', header)
  if length == 0 or length > max_response_bytes:
    raise ValueError(f'Invalid response length: {length}')
  body = recv_exact(sock, length)
  parsed = json.loads(decrypt(body))
  if not isinstance(parsed, dict):
    raise ValueError('Response JSON is not an object')
  return parsed


def check_ack(response: Dict[str, Any], section: str, method: str) -> Dict[str, Any]:
  """Validates TP-Link response structure and err_code == 0."""
  sec = response.get(section)
  if not isinstance(sec, dict):
    raise ValueError(f'Missing response section {section!r}')
  res = sec.get(method)
  if not isinstance(res, dict):
    raise ValueError(f'Missing response method {method!r}')
  if 'err_code' not in res:
    raise ValueError(f'Missing err_code in {section}.{method} response')
  err_code = res['err_code']
  if isinstance(err_code, bool) or err_code != 0:
    raise RuntimeError(f'Device rejected {section}.{method}: err_code={err_code}')
  return res
