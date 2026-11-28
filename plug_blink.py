#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import logging
import socket
import sys
import time
from typing import Any, Dict

import kasa_transport

# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
  'sysinfo': '{"system":{"get_sysinfo":null}}',
}

SMARTPLUG_PORT = kasa_transport.SMARTPLUG_PORT


class SmartPlug:
  def __init__(self, host: str, port: int = SMARTPLUG_PORT, timeout: int = 5):
    self.host = host
    self.port = port
    self.timeout = timeout

  @staticmethod
  def encrypt(string: str) -> bytes:
    return kasa_transport.encrypt(string)

  @staticmethod
  def decrypt(data: bytes) -> str:
    return kasa_transport.decrypt(data)

  def _send_command(self, command_str: str) -> Dict[str, Any]:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
      sock.settimeout(self.timeout)
      try:
        sock.connect((self.host, self.port))
        return kasa_transport.send_command(sock, self.encrypt(command_str))
      except socket.error as e:
        logging.error('Socket error connecting to %s: %s', self.host, e)
        raise

  def get_relay_state(self) -> int:
    data = self._send_command(COMMANDS['sysinfo'])
    info = kasa_transport.check_ack(data, 'system', 'get_sysinfo')
    state = info.get('relay_state')
    if state not in (0, 1) or isinstance(state, bool):
      raise ValueError(f'Unexpected relay_state: {state!r}')
    return state

  def set_relay_state(self, state: int) -> None:
    if state not in (0, 1) or isinstance(state, bool):
      raise ValueError(f'Invalid relay state: {state!r}')
    cmd = '{"system":{"set_relay_state":{"state":' + str(state) + '}}}'
    data = self._send_command(cmd)
    kasa_transport.check_ack(data, 'system', 'set_relay_state')


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

  if args.blinks < 1:
    parser.error('--blinks must be >= 1')
  if args.delay < 0:
    parser.error('--delay must be >= 0')

  plug = SmartPlug(args.smartplug)
  original_relay_state = None
  current_state = None
  exit_code = 0

  try:
    logging.info('Connected to smartplug (%s)', args.smartplug)
    original_relay_state = plug.get_relay_state()
    logging.info('Original state is "%s"',
                 'on' if original_relay_state else 'off')

    current_state = original_relay_state
    toggles = args.blinks

    for i in range(toggles):
      next_state = current_state ^ 1
      logging.info('Setting smartplug state to "%s" (Commit %d/%d).',
                   'on' if next_state else 'off', i + 1, toggles)
      plug.set_relay_state(next_state)
      current_state = next_state
      time.sleep(args.delay / 1000)

  except KeyboardInterrupt:
    logging.warning('Interrupted; restoring original relay state.')
    exit_code = 130
  except Exception as e:
    logging.error(f'An error occurred: {e}')
    exit_code = 1
  finally:
    if original_relay_state is not None and current_state != original_relay_state:
      try:
        logging.info('Returning to original state "%s".',
                     'on' if original_relay_state else 'off')
        plug.set_relay_state(original_relay_state)
      except Exception as restore_err:
        logging.error('Failed to restore original state "%s": %s',
                      'on' if original_relay_state else 'off', restore_err)
        exit_code = 1

  if exit_code:
    sys.exit(exit_code)


if __name__ == '__main__':
  main()
