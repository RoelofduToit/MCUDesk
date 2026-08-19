# MCUDesk Long-Run Validation

Use this checklist for a real 8–12 hour validation before packaging or release. Automated tests exercise lifecycle and high-rate data paths, but they cannot reproduce USB drivers, host sleep, cable quality, disk behavior, or hardware timing.

## Primary overnight test

Recommended equipment and stream:

- Raspberry Pi Pico or similar USB serial device
- 9 numeric CSV thermocouple channels
- approximately 1 sample per second
- 8–12 hour duration

Before starting:

1. Note the MCUDesk version, OS, available disk space, and process memory.
2. Connect the device and confirm one update per second in Terminal, Data, Dashboard, and Graphs.
3. Select several graph channels and confirm the graph starts at elapsed time zero.
4. Enter a meaningful session name and start recording in a location with ample free space.
5. Confirm the session contains `session.json` plus the device directory with growing `raw.log` and `data.csv` files.
6. Leave the machine awake and disable automatic suspend for the test only.

During the run, check at least once that:

- the application remains responsive;
- RX and logged-byte counters continue increasing;
- `raw.log` and `data.csv` continue growing;
- graph history remains a rolling one-hour window;
- process memory reaches a stable range rather than continuously climbing;
- no repeated modal errors or console traceback appears.

After the run:

1. Stop recording while leaving the serial device connected.
2. Verify both data files close cleanly and `session.json` reports `completed`, a normal end reason, end timestamps, duration, byte totals, and row count.
3. Compare the structured row count with the expected duration and device rate, allowing for startup and transport variation.
4. Confirm elapsed times are monotonic and inspect the start, middle, and end of `data.csv`.
5. Disconnect and reconnect the device several times; confirm updates occur once per sample after every reconnect.
6. Open the completed session in Replay and verify channel identities, aliases, units, alarms, Dashboard values, and graphs.
7. Record final process memory and note any missing blocks, UI stalls, or driver errors.

## Failure and shutdown checks

- While recording, unplug the device. Confirm one concise error, finalized files, a source-specific disconnect reason, and a successful later reconnect.
- Start another recording and close MCUDesk. Cancel once to confirm acquisition continues, then close again and confirm exit. Verify the recording is finalized with `application_closed`.
- If safely possible in a disposable test location, make the destination unwritable during a run. Confirm recording becomes inactive for the affected source and the GUI remains usable. Restore permissions afterward.

## Optional two-device test

Connect a Pico and an Arduino at different sample rates. Start one named recording and verify separate device directories with a shared parent session origin. Unplug only one device midway through the run. Its logger should finalize with `serial_disconnected`; the other device must continue acquiring and recording until manually stopped. Replay should restore both independent source identities and their complete available data.

## Known limitations

- There is no proactive low-disk-space monitor yet; disk-full is reported when an operating-system file write or flush fails.
- Live graph history has a one-hour time window and an emergency per-channel point ceiling; recording files are not capped.
- Replay loads structured CSV into memory. Very large or very high-rate multi-day sessions may require substantial RAM.
- Data and Dashboard presentation updates are not yet coalesced at a fixed frame rate, although graph drawing is timer-driven and logging remains independent.
