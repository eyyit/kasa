# kasa — Agent Map

TP-Link Kasa smart plug control utilities, follower tracker daemon, power meter poller, and Nagios check.

## Validation Gate
- Run all offline unit tests:
  ```sh
  make check
  ```
- Tests must remain completely offline and never connect to real smart plugs.

## Repository Layout
- `kasa_transport.py`, `kasa_transport_test.py` — framed TCP transport, exact reads, XOR encoding, bounded lengths, and explicit `err_code == 0` acknowledgment validation.
- `plug_tracker.py`, `plug_tracker_test.py`, `plug_tracker.service` — scheduled leader/follower plug state synchronization daemon and tests.
- `plug_blink.py`, `plug_blink_test.py` — plug blink control utility and tests.
- `plug_toggle.py`, `nagios_plug_check.py`, `power_usage.py`, `power_usage.service` — operational CLI/service entrypoints.

## Safety & Deployment Rules
- Require explicit successful acknowledgments (`err_code == 0`); failed follower updates must remain retryable rather than advancing state.
- `plug_toggle.py` and `nagios_plug_check.py` execute at import time; refactor behind `main()` before importing them into new tests.
- Never run operational scripts against physical plugs during validation.
