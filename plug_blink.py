#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import json
import logging
import socket
import sys
import time
from datetime import datetime, timedelta
from struct import pack

def encrypt(string):
  key = 171
  result = pack('>I', len(string))
  for i in string:
    a = key ^ ord(i)
    key = a
    result += bytes([a])
  return result


def decrypt(string):
  key = 171
  result = ''
  for i in string:
    a = key ^ i
    key = i
    result += chr(a)
  return result


def query_smartplug(sock):
  sock.send(COMMANDS['sysinfo'])
  str_data = sock.recv(2048)
  decrypted = decrypt(str_data[4:])
  data = json.loads(decrypted)
  relay_state = data['system']['get_sysinfo']['relay_state']
  return relay_state


def setup_socket(ip):
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.settimeout(1)
  sock.connect((ip, SMARTPLUG_PORT))
  return sock


def set_state(sock, desired_state):
  logging.info('Setting smartplug state to "%s".', STATES[desired_state])
  sock.send(COMMANDS['state'][desired_state])
  logging.info('Done.')


# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMANDS = {
    'state': {
      0: encrypt('{"system":{"set_relay_state":{"state":0}}}'),
      1: encrypt('{"system":{"set_relay_state":{"state":1}}}'),
    },
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

SMARTPLUG_PORT = 9999

STATES = ['off', 'on']

logging.basicConfig(
    format='%(levelname).1s%(asctime)s %(lineno)d]  %(message)s',
    level=logging.INFO, datefmt='%H:%M:%S')
parser = argparse.ArgumentParser()
parser.add_argument('-s', '--smartplug', required=True,
                    help='Smartplug hostname or IP address.')
parser.add_argument('--blinks', type=int, default=5,
                    help='Number of cycles to perform.')
parser.add_argument('--delay', type=int, default=200,
                    help='Milliseconds to delay between cycles.')
args = parser.parse_args()

sock = setup_socket(args.smartplug)
logging.info('Connected to smartplug (%s)', args.smartplug)
original_relay_state = query_smartplug(sock)
relay_state = original_relay_state
logging.info('Original state is "%s"', STATES[relay_state])
for blink in range(args.blinks + 1):
  relay_state ^= 1  # Toggle it.
  set_state(sock, relay_state)
  time.sleep(args.delay / 1000)
if original_relay_state != relay_state:
  set_state(sock, original_relay_state)
sock.close()
