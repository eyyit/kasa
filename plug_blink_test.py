#!/usr/bin/python3
import unittest
from unittest.mock import MagicMock, patch, call
import socket
import json
import struct

import plug_blink


class TestSmartPlug(unittest.TestCase):
  def setUp(self):
    self.host = '192.168.1.100'
    self.plug = plug_blink.SmartPlug(self.host)

  def test_encrypt_decrypt(self):
    """Test that encryption and decryption are reversible."""
    original = '{"system":{"get_sysinfo":null}}'
    encrypted = plug_blink.SmartPlug.encrypt(original)
    decrypted = plug_blink.SmartPlug.decrypt(encrypted[4:]) # Skip length header
    self.assertEqual(original, decrypted)

  def test_init(self):
    """Test initialization defaults."""
    p = plug_blink.SmartPlug('1.2.3.4')
    self.assertEqual(p.host, '1.2.3.4')
    self.assertEqual(p.port, plug_blink.SMARTPLUG_PORT)
    self.assertEqual(p.timeout, 5)

  @patch('socket.socket')
  def test_send_command(self, mock_socket_cls: MagicMock):
    """Test sending a command handling framed/fragmented TCP reads."""
    mock_sock = MagicMock()
    mock_socket_cls.return_value.__enter__.return_value = mock_sock

    response_data = '{"system":{"test":1}}'
    encrypted_response = plug_blink.SmartPlug.encrypt(response_data)
    # Deliver 2-byte header fragment first, then remainder to prove framing works
    mock_sock.recv.side_effect = [encrypted_response[:2], encrypted_response[2:4], encrypted_response[4:]]

    result = self.plug._send_command('test_command')

    mock_sock.connect.assert_called_with((self.host, plug_blink.SMARTPLUG_PORT))
    self.assertTrue(mock_sock.sendall.called)
    self.assertEqual(result, {'system': {'test': 1}})

  @patch('plug_blink.SmartPlug._send_command')
  def test_get_relay_state(self, mock_send: MagicMock):
    """Test parsing the relay state with err_code check."""
    mock_send.return_value = {'system': {'get_sysinfo': {'err_code': 0, 'relay_state': 1}}}
    state = self.plug.get_relay_state()
    self.assertEqual(state, 1)
    mock_send.assert_called_with(plug_blink.COMMANDS['sysinfo'])

    mock_send.return_value = {'system': {'get_sysinfo': {'err_code': 0, 'relay_state': 0}}}
    state = self.plug.get_relay_state()
    self.assertEqual(state, 0)

  @patch('plug_blink.SmartPlug._send_command')
  def test_set_relay_state(self, mock_send: MagicMock):
    """Test setting the relay state validates err_code == 0."""
    mock_send.return_value = {'system': {'set_relay_state': {'err_code': 0}}}
    self.plug.set_relay_state(1)
    expected_cmd = '{"system":{"set_relay_state":{"state":1}}}'
    mock_send.assert_called_with(expected_cmd)

    self.plug.set_relay_state(0)
    expected_cmd_0 = '{"system":{"set_relay_state":{"state":0}}}'
    mock_send.assert_called_with(expected_cmd_0)

    mock_send.return_value = {'system': {'set_relay_state': {'err_code': -1}}}
    with self.assertRaises(RuntimeError):
      self.plug.set_relay_state(1)

  @patch('plug_blink.time.sleep', side_effect=KeyboardInterrupt)
  @patch('plug_blink.SmartPlug')
  def test_main_restores_original_state_on_interrupt(self, mock_plug_cls: MagicMock, _mock_sleep: MagicMock):
    """M-40: KeyboardInterrupt after first toggle must restore original relay state."""
    plug = MagicMock()
    plug.get_relay_state.return_value = 0
    mock_plug_cls.return_value = plug
    with patch('sys.argv', ['plug_blink.py', '-s', '192.168.1.100', '--blinks', '3', '--delay', '10']):
      with self.assertRaises(SystemExit) as cm:
        plug_blink.main()
    self.assertEqual(cm.exception.code, 130)
    self.assertEqual(plug.set_relay_state.call_args_list, [call(1), call(0)])

  @patch('logging.error')
  @patch('socket.socket')
  def test_connection_error(
    self, mock_socket_cls: MagicMock, mock_logging: MagicMock,
  ):
    """Test that socket errors are raised."""
    mock_sock = MagicMock()
    mock_socket_cls.return_value.__enter__.return_value = mock_sock
    mock_sock.connect.side_effect = socket.error("Connection refused")

    with self.assertRaises(socket.error):
      self.plug._send_command('foo')


if __name__ == '__main__':
  unittest.main()
