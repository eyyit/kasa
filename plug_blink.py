#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import json
import logging
import socket
import struct
import time
import sys
from typing import Dict, Any, Union

# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
  'sysinfo': '{"system":{"get_sysinfo":null}}',
}

SMARTPLUG_PORT = 9999


class SmartPlug:
  def __init__(self, host: str, port: int = SMARTPLUG_PORT, timeout: int = 5):
    self.host = host
    self.port = port
    self.timeout = timeout

  @staticmethod
  def encrypt(string: str) -> bytes:
    key = 171
    result = struct.pack('>I', len(string))
    for char in string:
      a = key ^ ord(char)
      key = a
      result += bytes([a])
    return result

  @staticmethod
  def decrypt(string: bytes) -> str:
    key = 171
    result = ''
    for char in string:
      a = key ^ char
      key = char
      result += chr(a)
    return result

  def _send_command(self, command_str: str) -> str:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.settimeout(self.timeout)
      try:
        sock.connect((self.host, self.port))
        sock.send(self.encrypt(command_str))
        data = sock.recv(2048)
        return self.decrypt(data[4:])
      except socket.error as e:
        logging.error('Socket error connecting to %s: %s', self.host, e)
        raise

  def get_relay_state(self) -> int:
    response = self._send_command(COMMANDS['sysinfo'])
    data = json.loads(response)
    return data['system']['get_sysinfo']['relay_state']

  def set_relay_state(self, state: int) -> None:
    cmd = '{"system":{"set_relay_state":{"state":' + str(state) + '}}}'
    self._send_command(cmd)


def main() -> None:
  logging.basicConfig(
    format='%(levelname).1s%(asctime)s %(lineno)d]  %(message)s',
    level=logging.INFO, datefmt='%H:%M:%S')

  parser = argparse.ArgumentParser(description="Blink a TP-Link SmartPlug")
  parser.add_argument('-s', '--smartplug', required=True,
                      help='Smartplug hostname or IP address.')
  parser.add_argument('--blinks', type=int, default=5,
                      help='Number of cycles to perform.')
  parser.add_argument('--delay', type=int, default=200,
                      help='Milliseconds to delay between cycles.')
  args = parser.parse_args()

  plug = SmartPlug(args.smartplug)

  try:
    logging.info('Connected to smartplug (%s)', args.smartplug)
    original_relay_state = plug.get_relay_state()
    logging.info('Original state is "%s"',
                 'on' if original_relay_state else 'off')

    current_state = original_relay_state
    toggles = args.blinks

    for i in range(toggles):
      current_state ^= 1
      logging.info('Setting smartplug state to "%s" (Commit %d/%d).',
                   'on' if current_state else 'off', i + 1, toggles)
      plug.set_relay_state(current_state)
      time.sleep(args.delay / 1000)

    if current_state != original_relay_state:
      logging.info('Returning to original state "%s".',
                   'on' if original_relay_state else 'off')
      plug.set_relay_state(original_relay_state)

  except Exception as e:
    logging.error(f'An error occurred: {e}')
    sys.exit(1)


if __name__ == '__main__':
  main()
