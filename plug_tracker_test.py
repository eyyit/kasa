#!/usr/bin/python3
import unittest
from datetime import datetime, time, timedelta
from unittest.mock import MagicMock, patch, call

import plug_tracker

class TestEncryption(unittest.TestCase):
  def test_encrypt_decrypt(self):
    original = '{"system":{"get_sysinfo":null}}'
    encrypted = plug_tracker.encrypt(original)
    decrypted = plug_tracker.decrypt(encrypted[4:])
    self.assertEqual(original, decrypted)

class TestScheduler(unittest.TestCase):
  def test_always_active_if_no_schedule(self):
    scheduler = plug_tracker.Scheduler([])
    self.assertTrue(scheduler.is_active(time(12, 0)))

  def test_single_window_active(self):
    # 08:00 to 10:00
    schedule = [(time(8, 0), time(10, 0))]
    scheduler = plug_tracker.Scheduler(schedule)
    self.assertTrue(scheduler.is_active(time(8, 0)))
    self.assertTrue(scheduler.is_active(time(9, 0)))
    self.assertTrue(scheduler.is_active(time(10, 0)))
    self.assertFalse(scheduler.is_active(time(7, 59)))
    self.assertFalse(scheduler.is_active(time(10, 1)))

  def test_multiple_windows(self):
    # 08:00-10:00 AND 20:00-22:00
    schedule = [
        (time(8, 0), time(10, 0)),
        (time(20, 0), time(22, 0))
    ]
    scheduler = plug_tracker.Scheduler(schedule)
    self.assertTrue(scheduler.is_active(time(9, 0)))
    self.assertTrue(scheduler.is_active(time(21, 0)))
    self.assertFalse(scheduler.is_active(time(12, 0)))

  def test_seconds_until_next_active(self):
    # 08:00-10:00
    schedule = [(time(8, 0), time(10, 0))]
    scheduler = plug_tracker.Scheduler(schedule)
    
    # Current time 07:00, next start is 08:00 (1 hr = 3600s)
    current = datetime(2023, 1, 1, 7, 0, 0)
    wait = scheduler.seconds_until_next_active(current)
    self.assertEqual(wait, 3600)

    # Current time 12:00, next start is 08:00 tomorrow (20 hrs = 72000s)
    current = datetime(2023, 1, 1, 12, 0, 0)
    wait = scheduler.seconds_until_next_active(current)
    self.assertEqual(wait, 72000)

  def test_seconds_until_next_active_multiple(self):
     # 08:00-10:00, 20:00-22:00
    schedule = [
        (time(8, 0), time(10, 0)),
        (time(20, 0), time(22, 0))
    ]
    scheduler = plug_tracker.Scheduler(schedule)
    
    # 12:00 -> next is 20:00 (8 hrs = 28800s)
    current = datetime(2023, 1, 1, 12, 0, 0)
    wait = scheduler.seconds_until_next_active(current)
    self.assertEqual(wait, 28800)

class TestPlugTracker(unittest.TestCase):
  @patch('plug_tracker.setup_logging')
  @patch('plug_tracker.SmartPlugClient')
  def test_tick_active_logic(self, mock_client_cls, mock_logging):
    # Mock scheduler to be always active
    mock_scheduler = MagicMock()
    mock_scheduler.is_active.return_value = True
    
    # Mock client behavior
    mock_leader = MagicMock()
    mock_follower = MagicMock()
    mock_client_cls.side_effect = [mock_leader, mock_follower]
    
    tracker = plug_tracker.PlugTracker(
        leader_ip='1.1.1.1',
        follower_ip='2.2.2.2',
        scheduler=mock_scheduler
    )
    
    # Scenario 1: Leader state 0 (default prev_state -1) -> Follower NOT updated
    # (initial sync skipped)
    mock_leader.get_relay_state.return_value = 0
    tracker.tick()
    mock_follower.set_relay_state.assert_not_called()
    self.assertEqual(tracker.prev_state, 0)
    
    # Scenario 2: Leader state stays 0 -> Follower NOT updated (optimization)
    mock_follower.reset_mock()
    tracker.tick()
    mock_follower.set_relay_state.assert_not_called()
    
    # Scenario 3: Leader state changes to 1 -> Follower updated
    mock_leader.get_relay_state.return_value = 1
    tracker.tick()
    mock_follower.set_relay_state.assert_called_with(1)

  def test_parse_range(self):
    # Test the static parsing method
    from plug_tracker import parse_time_range
    start, end = parse_time_range('08:00-10:00')
    self.assertEqual(start, time(8, 0))
    self.assertEqual(end, time(10, 0))

if __name__ == '__main__':
  unittest.main()
