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


# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

STATES = ['off', 'on']

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--smartplug', required=True,
                    help='Smartplug hostname or IP address.')
parser.add_argument('--on', action='store_true', default=False,
                    help='Alert if plug is not ON.')
parser.add_argument('--off', action='store_true', default=False,
                    help='Alert if plug is not OFF.')
parser.add_argument('-v', '--verbose', action='store_true', default=False,
                    help='Show debugging output.')
args = parser.parse_args()

loglevel = logging.DEBUG if args.verbose else logging.ERROR
logging.basicConfig(
    format='%(levelname).1s%(asctime)s %(lineno)d]  %(message)s',
    level=loglevel, datefmt='%H:%M:%S')

if not (args.on or args.off):
  parser.error('Specify --on or --off.')

error_msg = ''
sock = None
try:
  sock = setup_socket(args.smartplug)
  relay_state = query_smartplug(sock)
except ConnectionRefusedError:
  error_msg = 'is UNREACHABLE'
except (TimeoutError, socket.timeout):
  error_msg = 'TIMED OUT'
except (OSError, ValueError, RuntimeError, KeyError) as e:
  error_msg = f'PROTOCOL ERROR ({e})'
finally:
  if sock is not None:
    try:
      sock.close()
    except OSError:
      pass

if error_msg:
  print(f'UNKNOWN: smartplug {args.smartplug} {error_msg}')
  sys.exit(3)

logging.debug('Connected to smartplug (%s)', args.smartplug)
relay_state_str = STATES[relay_state].upper()
logging.debug('State is "%s"', relay_state_str)
status_str = f'smartplug {args.smartplug} is {relay_state_str}'

for status in ((args.on, 0), (args.off, 1)):
  if status[0] and relay_state == status[1]:
    print(f'CRITICAL: {status_str}')
    sys.exit(2)
print(f'OK: {status_str}')
sys.exit(0)
