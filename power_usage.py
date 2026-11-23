#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import json
import logging
import socket
import sys
import time
from struct import pack

def setup_logging(log_path):
  logging.basicConfig(
      level=logging.INFO,
      format='%(levelname).1s%(asctime)s %(lineno)-3s]  %(message)s',
      datefmt='%Y-%m-%d_%H:%M:%S',
      handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
  )


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

def setup_socket(ip):
  while True:
    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(1)
      sock.connect((ip, SMARTPLUG_PORT))
    except:
      logging.error('Could not connect to host %s', args.smartplug)
      time.sleep(1)
      continue
    break
  logging.info('Connected to smartplug at %s', ip)
  return sock

def query_smartplug(sock):
  sock.send(COMMAND)
  str_data = sock.recv(2048)
  data = json.loads(decrypt(str_data[4:]))
  return data['emeter']['get_realtime']

setup_logging('/var/log/cron/power_usage.log')
# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMAND = encrypt('{"emeter":{"get_realtime":{}}}')
SMARTPLUG_PORT = 9999

parser = argparse.ArgumentParser()
parser.add_argument('-s', '--smartplug', required=True,
                    help='Smartplug hostname or IP address to query.')
args = parser.parse_args()

sock = setup_socket(args.smartplug)

while True:
  try:
    emeter = query_smartplug(sock)
  except:
    logging.error('Error getting data from %s', args.smartplug)
    sock.close()
    sock = setup_socket(args.smartplug)
  data = []
  for k,v in emeter.items():
    data.append(f'smartplug_power.computer.{k} {v} -1.')
  logging.info(data)
  time.sleep(1)
