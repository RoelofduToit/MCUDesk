# MCUDesk Diagnostics

Diagnostics measures whether incoming data is healthy, timely, and being parsed.
It does not change engineering measurements, raw serial bytes, Device Profiles,
or recorded samples.

Open **Tools → Diagnostics...**. The main window stays the same.

## What is measured

Per source:

- connection state and uptime
- bytes and newline-delimited messages received
- structured updates
- parser errors (malformed lines only)
- reconnect count
- last RX / structured activity
- approximate RX and message rates over a short window
- longest observed activity gap

Per structured channel:

- update count
- measured rate from inter-arrival intervals
- average interval
- longest interval
- current age
- jitter (sample standard deviation of recent intervals)
- OK / STALE

Rates use **monotonic** time. They are not inferred from channel names or units.

## Stale and gaps

Default stale threshold: **5 ×** the recent median interval, after at least five
samples. Optional expected interval (Diagnostics dialog) replaces the measured
baseline.

A **data gap** is recorded when a new sample arrives after an interval of
**5 ×** the baseline. Ordinary jitter does not create a gap.

Stale means the channel has not updated recently. It does not mean the value is
zero, and MCUDesk does not invent values while stale.

## Parser errors

A line that produces no structured update is not automatically an error. Debug
text is **unrecognized**. **Parser errors** are malformed lines: invalid JSON
that looks like JSON, CSV decode failures, or oversized discarded lines.

Parser success rate is `structured / (structured + malformed)`. Unrecognized
debug lines are excluded.

## Session metadata

When a recording stops, a compact `diagnostics` summary may be written into
`session.json`. Replay does not require it. Old sessions without diagnostics
still load. Diagnostics never writes into `events.csv`.

## Graph markers

Vertical graph gap markers are deferred. Use the Diagnostics dialog for gap
history.
