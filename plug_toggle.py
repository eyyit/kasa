#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import logging
import socket
import sys

from kasa_transport import (
    SMARTPLUG_PORT,
    check_ack,
    decrypt,
    encrypt,
    send_command,
)


def query_smartplug(sock):
  data = send_command(sock, COMMANDS['sysinfo'])
  sysinfo = check_ack(data, 'system', 'get_sysinfo')
  relay_state = sysinfo['relay_state']
  if relay_state not in (0, 1):
    raise ValueError(f'Invalid relay_state: {relay_state!r}')
  return int(relay_state)


def setup_socket(ip):
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(2.0)
  sock.connect((ip, SMARTPLUG_PORT))
  return sock


def set_state(sock, desired_state):
  logging.info('Setting smartplug state to "%s".', STATES[desired_state])
  data = send_command(sock, COMMANDS['state'][desired_state])
  check_ack(data, 'system', 'set_relay_state')
  logging.info('Done.')


# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'state': {
      0: encrypt('{"system":{"set_relay_state":{"state":0}}}'),
      1: encrypt('{"system":{"set_relay_state":{"state":1}}}'),
    },
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

STATES = ['off', 'on']

logging.basicConfig(
    format='%(levelname).1s%(asctime)s %(lineno)d]  %(message)s',
    level=logging.INFO, datefmt='%H:%M:%S')
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--smartplug', required=True,
                    help='Smartplug hostname or IP address.')
parser.add_argument('--on', action='store_true', default=False,
                    help='Turn on.')
parser.add_argument('--off', action='store_true', default=False,
                    help='Turn off.')
args = parser.parse_args()

sock = setup_socket(args.smartplug)
logging.info('Connected to smartplug (%s)', args.smartplug)
relay_state = query_smartplug(sock)
logging.info('State is "%s"', STATES[relay_state])
if args.on and relay_state == 0:
  set_state(sock, 1)
if args.off and relay_state == 1:
  set_state(sock, 0)
sock.close()
