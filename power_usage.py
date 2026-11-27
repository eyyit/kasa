#!/usr/bin/python3
# Copied and modified from https://github.com/softScheck/tplink-smartplug

import argparse
import logging
import socket
import sys
import time

from kasa_transport import (
    SMARTPLUG_PORT,
    check_ack,
    decrypt,
    encrypt,
    send_command,
)

def setup_logging(log_path):
  logging.basicConfig(
      level=logging.INFO,
      format='%(levelname).1s%(asctime)s %(lineno)-3s]  %(message)s',
      datefmt='%Y-%m-%d_%H:%M:%S',
      handlers=[logging.FileHandler(log_path), logging.StreamHandler(sys.stdout)],
  )


def setup_socket(ip):
  while True:
    try:
      sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
      sock.settimeout(1)
      sock.connect((ip, SMARTPLUG_PORT))
    except OSError as e:
      logging.error('Could not connect to host %s: %s', ip, e)
      time.sleep(1)
      continue
    break
  logging.info('Connected to smartplug at %s', ip)
  return sock

def query_smartplug(sock):
  data = send_command(sock, COMMAND)
  return check_ack(data, 'emeter', 'get_realtime')

# https://github.com/softScheck/tplink-smartplug/blob/master/tplink-smarthome-commands.txt
COMMAND = encrypt('{"emeter":{"get_realtime":{}}}')

def main():
  setup_logging('/var/log/cron/power_usage.log')

  parser = argparse.ArgumentParser()
  parser.add_argument('-s', '--smartplug', required=True,
                      help='Smartplug hostname or IP address to query.')
  args = parser.parse_args()

  sock = setup_socket(args.smartplug)

  while True:
    try:
      emeter = query_smartplug(sock)
    except Exception as e:
      logging.error('Error getting data from %s: %s', args.smartplug, e)
      try:
        sock.close()
      except OSError:
        pass
      sock = setup_socket(args.smartplug)
      time.sleep(1)
      continue
    data = []
    for k, v in emeter.items():
      data.append(f'smartplug_power.computer.{k} {v} -1.')
    logging.info(data)
    time.sleep(1)


if __name__ == '__main__':
  main()
