# Export

MCUDesk can export the current Graphs selection without changing acquisition,
recording, or replay.

## Selected Data (CSV)

File → Export → Selected Data...

Writes actual stored measurements for channels currently selected on Graphs.

- Live: measurements retained in graph history (up to one hour / 200,000 points
  per channel).
- Replay: recorded structured samples from the loaded session.

Range:

- **Current graph time window** uses the visible Graphs elapsed-time range,
  including zoom.
- **All retained data** uses every stored sample for the selected channels.

Rows are the union of actual sample timestamps. If a channel has no stored
value at that time, the CSV cell is empty. MCUDesk does not interpolate,
smooth, forward-fill, or insert zeros.

Graph smoothing and interpolation never change CSV contents.

Absolute wall-clock timestamps are not exported. Elapsed time is the
authoritative time column.

## Current Graph (PNG / SVG)

File → Export → Current Graph...

Exports the current Graphs plot appearance, including visible traces, axes,
legend, event markers, and any enabled smoothing or interpolation. This is a
visual figure, not a measurement table.

The export does not include MCUDesk chrome (menus, connection bar, graph
controls). It does not change the current graph view.
