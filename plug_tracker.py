#!/usr/bin/python3
"""
Plug Tracker

Monitors a 'leader' smartplug and mirrors its state to a 'follower' smartplug.
Can be configured to be active only during specific time windows.

Copied and modified from https://github.com/softScheck/tplink-smartplug
"""

import argparse
import json
import logging
import socket
import sys
import time
from datetime import datetime, timedelta, date, time as dt_time
from struct import pack
from typing import List, Tuple, Optional, Dict, Any

# Adjust path to find mypylib if needed
sys.path.append('/opt/repos/mypylib')
try:
  from mypylib import setup_logging
except ImportError:
  # Fallback for local testing if mypylib is not present
  def setup_logging(log_path: str) -> None:
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(message)s'
    )


def encrypt(string: str) -> bytes:
  """Encrypts a string for TP-Link smartplug protocol."""
  key = 171
  result = pack('>I', len(string))
  for i in string:
    a = key ^ ord(i)
    key = a
    result += bytes([a])
  return result


def decrypt(string: bytes) -> str:
  """Decrypts a byte string from TP-Link smartplug protocol."""
  key = 171
  result = ''
  for i in string:
    a = key ^ i
    key = i
    result += chr(a)
  return result


COMMANDS = {
    'state': {
        0: encrypt('{"system":{"set_relay_state":{"state":0}}}'),
        1: encrypt('{"system":{"set_relay_state":{"state":1}}}'),
    },
    'sysinfo': encrypt('{"system":{"get_sysinfo":null}}'),
}

SMARTPLUG_PORT = 9999


class SmartPlugClient:
  """Client for interacting with a TP-Link smartplug."""

  def __init__(self, ip: str):
    self.ip = ip

  def _connect(self) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)
    sock.connect((self.ip, SMARTPLUG_PORT))
    return sock

  def get_relay_state(self) -> int:
    """Queries the smartplug for its relay state (0 or 1)."""
    sock = self._connect()
    try:
      sock.send(COMMANDS['sysinfo'])
      # Receive header to know length, or just read a chunk
      data = sock.recv(2048)
      decrypted = decrypt(data[4:])
      json_data = json.loads(decrypted)
      return json_data['system']['get_sysinfo']['relay_state']
    finally:
      sock.close()

  def set_relay_state(self, state: int) -> None:
    """Sets the smartplug relay state."""
    sock = self._connect()
    try:
      sock.send(COMMANDS['state'][state])
    finally:
      sock.close()


class Scheduler:
  """Manages active time windows."""

  def __init__(self, active_windows: List[Tuple[dt_time, dt_time]]):
    # active_windows is a list of (start_time, end_time) tuples
    self.active_windows = active_windows
    # If no windows provided, we are always active
    self.always_active = len(active_windows) == 0

  def is_active(self, current_time: dt_time) -> bool:
    """Checks if the current time is within any active window."""
    if self.always_active:
      return True

    for start, end in self.active_windows:
      if start <= end:
        if start <= current_time <= end:
          return True
      else:  # Window crosses midnight
        if current_time >= start or current_time <= end:
          return True
    return False

  def seconds_until_next_active(self, current_dt: datetime) -> int:
    """Calculates seconds until the next active window starts."""
    if self.always_active:
      return 0

    current_time = current_dt.time()
    min_wait_seconds = float('inf')

    found_window = False

    for start, _ in self.active_windows:
      # If start time is later today
      if start > current_time:
        next_start = datetime.combine(current_dt.date(), start)
      else:
        # Start time is tomorrow
        next_start = datetime.combine(
            current_dt.date() + timedelta(days=1), start)
      
      wait = (next_start - current_dt).total_seconds()
      if wait < min_wait_seconds:
        min_wait_seconds = wait
        found_window = True
    
    # Also handle case where we might be *in* a window? 
    # The caller typically calls this only when !is_active().
    # But if calling blindly, we should check if we are already active?
    # Spec says: "not be running" if not active.

    return int(min_wait_seconds) if found_window else 0


class PlugTracker:
  """Main application logic for tracking and mirroring plug state."""

  def __init__(self, leader_ip: str, follower_ip: str, scheduler: Scheduler):
    self.leader_client = SmartPlugClient(leader_ip)
    self.follower_client = SmartPlugClient(follower_ip)
    self.scheduler = scheduler
    self.prev_state = -1

  def run(self) -> None:
    """Main loop."""
    logging.info('PlugTracker started.')
    
    while True:
      now = datetime.now()
      
      if not self.scheduler.is_active(now.time()):
        wait_seconds = self.scheduler.seconds_until_next_active(now)
        logging.info(
            'Outside active hours. Sleeping for %d seconds.', wait_seconds)
        time.sleep(wait_seconds)
        logging.info('Waking up. Resuming operations.')
        self.prev_state = -1  # Reset state on wake
        continue

      try:
        self.tick()
      except Exception as e:
        logging.error('Error in tick: %s', e)
        # Sleep a bit to avoid rapid looping on error
        time.sleep(5)

      time.sleep(1)

  def tick(self) -> None:
    """Single iteration of checking and updating."""
    try:
      leader_state = self.leader_client.get_relay_state()
    except (socket.error, socket.timeout) as e:
      logging.warning('Could not connect to leader: %s', e)
      return

    if leader_state != self.prev_state:
      if self.prev_state != -1:
        logging.info(
            'Leader changed to %d. Updating follower.', leader_state)
        try:
          self.follower_client.set_relay_state(leader_state)
        except (socket.error, socket.timeout) as e:
          logging.error('Failed to update follower: %s', e)
      self.prev_state = leader_state


def parse_time_range(arg: str) -> Tuple[dt_time, dt_time]:
  """Parses a time range string like '08:00-10:00'."""
  try:
    start_str, end_str = arg.split('-')
    start_time = datetime.strptime(start_str.strip(), '%H:%M').time()
    end_time = datetime.strptime(end_str.strip(), '%H:%M').time()
    return start_time, end_time
  except ValueError:
    raise argparse.ArgumentTypeError(
        f"Invalid time range: '{arg}'. Format must be HH:MM-HH:MM")


def main() -> None:
  parser = argparse.ArgumentParser(
      description='Mirror a leader smartplug state to a follower.')
  parser.add_argument(
      '-l', '--leader', required=True,
      help='Leader smartplug IP/Hostname')
  parser.add_argument(
      '-f', '--follower', required=True,
      help='Follower smartplug IP/Hostname')
  parser.add_argument(
      '--active', action='append', type=parse_time_range,
      help='Active time window HH:MM-HH:MM. Can be specified multiple times.')
  parser.add_argument(
      '--logfilename', default='plug_tracker.log',
      help='Log filename (default: plug_tracker.log)')

  args = parser.parse_args()

  setup_logging(f'/var/log/cron/{args.logfilename}')

  schedule = args.active if args.active else []
  scheduler = Scheduler(schedule)

  tracker = PlugTracker(args.leader, args.follower, scheduler)
  
  try:
    tracker.run()
  except KeyboardInterrupt:
    logging.info('Stopping PlugTracker.')


if __name__ == '__main__':
  main()
