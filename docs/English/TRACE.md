# Trace and replay

[← Back to the README](../../README.md)

SerialHex can **record** every frame sent and received in a time-stamped file (the trace), **edit** it in the Replay panel, then **replay** the sends of this trace at the same pace, comparing the responses received with the recorded ones.

| File | Role |
|---|---|
| `core/trace/` | Recording, reading back, timing analysis, comparison; `document.py`: editing and renaming rules |
| `ui/replay/` | "Replay" panel: display, editing, row detail, replay |
| `traces/` | Suggested folder for the traces (ignored by Git) |

## Recording a trace

1. In the monitor, click **● Trace** and choose the file (default `traces/trace_YYYYMMDD_HHMMSS.csv`).
2. Use SerialHex as usual: every TX and RX frame is recorded, whatever its origin (Manual tab, Protocol tab, free hex, replay).
3. Click **■ Stop trace**. The monitor shows the number of frames and the file, and the trace opens in the **Replay** panel, shown on the right (unless another trace is being edited there).

Each frame is written to disk immediately: nothing is lost if the program is closed while recording.

### File format

CSV, separator `;`, readable and editable in Excel:

```
t_ms;delta_ms;dir;len;hex;label
0.0;0.0;TX;8;01 03 00 00 00 02 C4 0B;Read setpoint and mode #0x01
41.9;41.9;RX;9;01 03 04 00 E6 00 01 DA 04;
264.5;222.6;TX;8;01 04 00 00 00 02 71 CB;Read measurements #0x01
```

| Column | Contents |
|---|---|
| `t_ms` | Time since the start of the recording, in ms |
| `delta_ms` | Time since the previous line, in ms (for reading) |
| `dir` | `TX` (sent) or `RX` (received) |
| `len` | Number of bytes |
| `hex` | The bytes |
| `label` | Name of the message sent (TX), optional |

A trace can also be written by hand: only `dir` and `hex` are required (`t_ms` missing = 0 ms gap), the `,` separator is accepted, and lines starting with `#` are comments.

## Replaying a trace

1. Connect to the serial port.
2. Tick **▶ Replay** to the right of the tabs (or the **+ Replay** button of the monitor, which also copies the monitor frames into it): the panel appears on the right half. Then **Open…** (a recorded trace, or a `.csv` made by **Save…** of the monitor).
3. Each line of the file is shown in the table (TX in blue, RX in purple), with the **timing analysis** above:
   `Duration 1.06 s · 5 TX · 4 RX · gap between sends (min / avg / max) 264 / 266 / 267 ms · response latency 42 / 52 / 62 ms · no response: 1`
4. Choose the **pace**:
   - **Original timing**: each request leaves with the same gap as in the trace, at a speed from x0.25 to x4 (x2 = twice as fast);
   - **Fixed delay**: the same delay between all requests.
   The "Delay" column shows, on each TX line, the delay applied before it is sent.
5. Playback buttons, under the edit bar: **⏭ Step by step** (blue), **▶ Replay** (green), **■ Stop** (red); a tooltip explains each one on hover. **▶ Replay**: TX lines are sent again one by one; the current line has the **▶** icon. RX lines are not sent, they are used as reference.
   **Step by step**: **⏭ Step by step** sends the request of the selected row (or the first one), then the button becomes **⏭ Next**: each click (or **F8**) sends the next request, with no automatic delay. The result of a request is shown when the timeout has elapsed, or at once if Next is clicked earlier. **■ Stop** leaves the step-by-step mode.
6. **Reply timeout** (500 ms by default, taken from the monitor): maximum delay between sending a request and its response. A later response does not count. After the last request, SerialHex also waits this delay for the last responses.

### Table

One row per line of the file. An exchange = a TX line and the RX lines following it (expected responses); the result of the replay is shown on the TX line.

| Column | Contents |
|---|---|
| (icon) | ▶ while sending, then the result: ✓, ≠, ✗, + |
| t (ms) | Time of the line in the trace |
| Dir | TX (sent) or RX (received) |
| Bytes (hex) / Label | Contents of the line |
| Result | Comparison, see below |
| Delay | Wait before sending during the replay (TX lines), in ms |
| Response received / Lat. | Response obtained during the replay and its latency |

As the panel is half-width, the last columns are reached with the horizontal scroll bar (or by widening the panel with the separator).

### Selected row: help for reading

Clicking a row shows its details under the table:

```
Line 4 · TX · t 624.8 ms · since the previous 113.1 ms · until the next 62.5 ms · Read measurements #0x01
01 04 00 00 00 02 71 CB              (protocol colours: header grey, COMMAND ID bold, CRC green)
request #0x01 · Read measurements · 4 B · CRC OK   => converted values
                                                          [Decode in Protocol]
```

- the **interval** with the row above and the row below;
- the frame in colour and its decoding by the current protocol (command, error code, converted values);
- **Decode in Protocol**: a **TX** row (complete request of the current protocol) is loaded in the **Request** part: command found from its COMMAND ID, REQUEST ID and DATA (raw, the fields show its decoding), editable then sendable again. An **RX** row (or a TX that is not a request of the protocol) is shown in the **Response** part, decoded field by field ("Follow received responses" is then unticked so that it stays displayed). The filled frame gets the **dark grey background** of the Replay panel; both frames go back to light grey as soon as a new command is chosen in TX CMD.
- **Decode** checkbox (next to **Compare**): same thing on each click on a table row, without the button (nothing is loaded during a replay).
- **■ Stop** is greyed out while nothing is running; **▶ Replay** is greyed out during a replay or step by step.

| Result | Icon | Colour | Meaning |
|---|---|---|---|
| identical | ✓ | — | Same bytes, received before the timeout |
| different | ≠ | **orange background** | Bytes concerned: `bytes 8-9: expected 80 BB, received 00 C8` |
| timeout | ✗ | **red background** | A response was expected, nothing received within the "Reply timeout" (a late response is reported: `response arrived after 620 ms`) |
| extra response | + | yellow background | Response received while the trace has none |
| none expected | ✓ | — | Neither expected nor received |

The final summary counts the results: `Replay finished: 3 identical, 1 different, 1 none expected`. Untick "Compare responses" to replay without comparison.

### Editing the trace

| Action | How |
|---|---|
| Edit a cell | **Double-click** on t, Dir, Bytes or Label; **Enter** confirms, **Esc** cancels. An invalid entry (hex, number) is reported and the field stays open |
| Add a line | **+ Add**: TX line after the selection, **"Fixed delay" ms after** the line above (the next lines are shifted by as much), with the bytes of the line above; the byte entry opens |
| Add from a tab | **→ Replay** (Protocol tab: the built request; Manual tab: the message with its values). Depending on the "→: insert after / replace" choice of the edit bar, the frame is **inserted after** the selected line (in the middle of the interval) or **replaces** the selected line (its time is kept). The label takes the name of the command or message |
| Delete | **Delete** button or **Del** key (multiple selection with Ctrl / Shift) |
| Move | **Up** / **Down**: the line changes place but the times stay in order (the two lines swap their contents, not their t) |
| Rename / save | The **Name** of the file is edited directly (without `.csv`). **Save** (or Enter) saves under this name, in the same folder: if the name changed, the file is **renamed**; if another file already has this name, SerialHex asks whether to **replace** it. A `*` shows unsaved changes; SerialHex reminds you before opening another trace or quitting |
| Save as… | Copy into another folder; the original is kept |
| New | Empty trace, to fill with **+ Add** or the **→ Replay** arrows; suggested name `new_trace_<date>_<time>` (editable), also used if the Name field is empty when saving |

The replay uses the displayed trace, saved or not. It cannot be edited during a replay.

### Good to know

- A response is attached to the **last request sent**: if the device answers more slowly than the gap between two requests, its response is counted for the next one. Slow the replay down (x0.5) or use a longer fixed delay.
- The replay sends exactly the recorded bytes again, REQUEST ID included.
- Values that change by themselves (temperatures, counters) show up as "different": this is expected, the Result column shows the bytes concerned.
- Frames sent by the replay go through the monitor and, if a trace is being recorded, are recorded: a replay can be traced to compare it afterwards.

## Use in a script

```python
from core.trace import load_trace, exchanges, analyze, replay_delays, compare

events = load_trace("traces/test.csv")
print(analyze(events).text())
for x, delay in zip(exchanges(events), replay_delays(exchanges(events), speed=2)):
    print(f"wait {delay:.0f} ms then send {x.tx.data.hex(' ')}")
print(compare(bytes.fromhex("01 03 02 12 34"), bytes.fromhex("01 03 02 12 35")))
# (False, 'octet 4 : attendu 34, reçu 35')   (messages of core/ are in French)

# Edit a trace without the interface (same rules as the Replay panel)
from core.trace import TraceDocument
doc = TraceDocument("traces")
doc.load("traces/test.csv")
row = doc.insert_after(2, "TX", bytes.fromhex("01 03 00 02 00 01 25 CA"), "added")  # t in the middle
doc.set_cell(0, "label", "Read power")
doc.save_as_name("test_v2")           # renames; FileExistsError if the name is taken
```

Tests: `tests/test_trace.py`.
