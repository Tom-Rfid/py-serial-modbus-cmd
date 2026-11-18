# Architecture

[← Back to the README](../../README.md)

## Tree

```
serialhex.py               entry point (start, --merge option)
requirements.txt
setup.bat / setup.ps1      prepares the .venv environment (Python 3.9 by default)
run.bat                    starts SerialHex with .venv
core/                      logic, without graphical interface
  frames.py                building the frames of free messages, checksums
  messages.py              loading / merging of Msg_*.json, duplicates
  request_message.py       "protocol" messages ("request" key), saving from the Protocol tab
  jsonc.py                 reading JSON with comments (// and /* */)
  framing.py               splitting received bytes into frames (silence, end delimiter)
  serial_link.py           ports, availability test, connection, reading
  port_filter.py           port filter (VID / PID, FTDI), Bluetooth hiding
  tcp_link.py              TCP link (Modbus TCP, gateways), same interface as SerialLink
  link_switch.py           serial OR TCP link, seen as a single link
  settings.py              persistent settings (settings.json)
  edition.py               reading edition.json (software version)
  protocol/                protocol engine, driven by protocols/*.json
    common.py              QUERY, RESPONSE, ProtocolError
    crc.py                 8 / 16 / 32-bit CRCs and sums
    fields.py              field description, file checks
    placement.py           final field order: "at" (byte, start, end), "after"
    bits.py                reading / writing bit fields (LENb, atb, bit_order)
    encoding.py            line encoding (Modbus ASCII: ":0103…\r\n")
    decoded.py             result of a decoding (Field, Decoded)
    builder.py             building a frame
    decoder.py             decoding a frame
    protocol.py            Protocol class, frame variants (M-Bus, PROFIBUS)
    loader.py              reading the files of protocols/
    default.py             built-in generic protocol (fallback)
    helpers.py             shortcuts, colours, summary
  commands/                command library (Msg_*.json: "commands", "errors")
    types.py               field types, arrays, sizes
    physical.py            factor, offset, decimals, min / max
    encode.py / decode.py  values ↔ bytes
    convert.py             raw DATA ↔ input text, integer, possible readings (raw_guess)
    library.py             Command, Library, reading the files, "protocol" key
    describe.py            one-line summary for the log
  trace/                   TX / RX trace and replay
    events.py              TraceEvent
    recorder.py            recording on the fly
    files.py               reading / writing a trace file
    analysis.py            exchanges, timing statistics, replay delays
    compare.py             comparing responses, timeout
    document.py            trace opened in the Replay panel: editing, renaming
ui/                        Tkinter interface
  app/                     main window (one App class in several parts)
    window.py              creating and placing the panels, "Colours…" button
    messages.py            messages of the Manual tab (loading, added files, saving)
    sending.py             sending, sequences, serial port reading, send buttons greyed out
    protocol.py            current protocol, library, reply timeout
    traces.py              trace, Replay panel, "→ Replay" arrows
    layout.py              separators, Replay panel shown / hidden, closing
  protocol/                Protocol tab
    panel.py               ProtocolPanel: creation, choice of the protocol
    query.py               Request (TX) part
    command_search.py      TX CMD: search while typing, suggestions, favourites
    response.py            Response (RX) part and monitor summaries
    widgets.py             FieldTable (frame table, editable in place)
    from_replay.py         Replay row loaded in the Request or the Response
    highlight.py           frame filled from the Replay on a dark grey background
    constants.py           labels and colours
  replay/                  Replay panel (to the right of the tabs)
    panel.py               ReplayPanel: links the elements below
    file_bar.py            open, name / rename, save
    options.py             pace, timeout, compare
    edit_bar.py            add, delete, move; choice of the arrow
    table.py               editable table
    detail.py              selected row: interval, colours, decoding
    player.py              replay engine (sends, receptions, verdicts)
    constants.py           colours, icons, columns
  com_panel.py             "Link" panel: serial or TCP
  i18n.py                  interface language: _() and tr()
  icon.py                  window icon (assets/icon.png)
  lang/en.json             English translations (texts and message patterns)
  messages_panel.py        message list (Manual tab)
  save_dialog.py           "Save the message" window (name, suggested Msg_ file)
  tooltip.py               tooltips
  params_panel.py          message parameters, preview, sending (Manual tab)
  hexview.py               hex frames in colour
  theme.py                 interface colours (adjustable, remembered), subscriptions
  color_dialog.py          "Colours…" page: sample, hex, palette, preview
  monitor_panel.py         TX/RX log, free hex
edition.json               software version: name, title, icon, default protocol (core/edition.py)
assets/icon.png            window icon (PNG, replaceable)
protocols/                 frame structure, one file per protocol (CONF_PROTOCOL.md)
  README_CONF.txt          every key and possible value, with examples (LISEZMOI_CONF.txt: French)
  *.json                   protocols shipped with the version (list in the README)
msgLibrary/
  msgManual/               standalone messages of the Manual tab (Msg_*.json, "messages" key)
  msgList/                 command lists of the protocols (Msg_*.json, "commands" key; one subfolder per protocol)
tools/
  hexterm.py               command-line hex terminal
  gen_test_vectors.py      generates tests/vectors.json
  gen_protocol_vectors.py  generates tests/protocol_vectors.json
tests/
  vectors.json             reference frames, shared with js/
  protocol_vectors.json    reference results of the protocol engine, shared with js/
  test_vectors.py          checks core/frames.py against the vectors
  test_protocol.py         tests of the protocol engine and of the files of protocols/
  test_protocol_vectors.py checks core/protocol against the vectors
  test_commands.py         tests of the command library
  test_trace.py            tests of the trace, the replay and TraceDocument
  test_links.py            frame splitting, JSON with comments, TCP link
  test_i18n.py             translations (every text of ui/ translated, message patterns)
  test_request_message.py  protocol messages, saving, duplicates
  test_ports.py            port filter (VID / PID, Bluetooth)
  data/                    shared test data (protocol, messages, commands of a fictitious device)
js/                        TypeScript package (see INTERFACE.md)
  src/core/                frames, messages, framer, jsonc (JSON with comments)
  src/core/protocol/       protocol engine: same split as core/protocol/
  src/link/                SerialLink and SerialTransport interface
  src/electron/            main process (serialport) and preload
  src/react/               React hooks
  examples/                complete React screen, main / preload extracts
  test/                    vitest tests, including the shared vectors
docs/Francais/             documentation in French
docs/English/              documentation in English
Claude_IA/                 instructions for Claude (CLAUDE.md) and project status (STATUS.md)
```

`core/` (Python) and `js/src/core/` (TypeScript) implement the same message format and the same protocol engine; `tests/vectors.json` and `tests/protocol_vectors.json` guarantee that they produce the same bytes (and the same error messages). After changing `core/frames.py` or `core/protocol/`, run `python tools/gen_test_vectors.py` / `python tools/gen_protocol_vectors.py` again, then the tests on both sides.

## Principle

The code is split into two layers:

- **`core/`** holds all the logic: building a frame, reading the message files, driving the serial port. It does not depend on Tkinter and can be reused in a script or in tests.
- **`ui/`** holds the interface. Each panel is independent and receives callback functions. Only `ui/app/` knows every panel and links them together.

Writing rules:
- one file per subject, short functions whose name says what they do, comments in French;
- big panels are **packages** (`ui/protocol/`, `ui/replay/`, `ui/app/`): a main class assembled from parts ("mixins") or small widgets, one file each;
- choices between several cases are written as `if / elif / else`: SerialHex is developed with Python 3.9 (minimum of the VS Code debugger) and stays compatible with **Python 3.8**; neither has `match / case` (Python 3.10). On the TypeScript side, `switch / case`;
- rules that do not depend on the display (validation, renaming, computations) go into `core/`, where they are tested without the interface.

```
            ┌──────────────────── ui/app/ ─────────────────────┐
            │  ComPanel                                        │
            │  tabs: Manual (MessagesPanel + ParamsPanel),     │
            │        Protocol (ui/protocol/)                   │
            │  Replay panel (ui/replay/)                       │
            │  MonitorPanel                                    │
            └────┬───────────┬───────────┬──────────┬──────────┘
                 │           │           │          │
       core/serial_link  core/messages  core/protocol  core/commands, core/trace
                   │
               pyserial
```

## `core/` modules

### `frames.py`
Pure functions, without state.

| Function | Role |
|---|---|
| `build_frame(msg, values)` | Assembles the frame of a message from the values of its parameters |
| `encode_param(name, pdef, value)` | Encodes a value according to its type (`u8`, `u16be`, `enum`…) |
| `checksum(algo, data)` | Computes a checksum (`xor8`, `sum8`, `crc16_modbus`…) |
| `defaults_for(msg)` | Default values of the parameters of a message |
| `parse_hex`, `to_hex`, `to_ascii` | Text ↔ bytes conversions |

### `messages.py`

| Function | Role |
|---|---|
| `load_messages(path)` | Loads and validates a file; the group comes from the file name |
| `load_folder(folder)` | Loads every `Msg_*.json`, returns `(messages, errors)` |
| `merge_messages(messages, new)` | Adds messages without duplicates (identical ones skipped; same name, different contents: `"display"` completed with the source file) |
| `merge_files(folder, out)` | Merges every file into a single one |

### `request_message.py`

"Protocol" messages (`"request"` key): `build_request(msg, values, protocol, kind)` builds the frame with the current protocol; `make_request_message`, `save_message_file`, `find_saved`, `unique_name`, `file_name_for` are used by the "Save…" button of the Protocol tab.

### `protocol/`

Request / response protocol engine: the frame structure comes from a file of `protocols/` (details: [PROTOCOL.md](PROTOCOL.md)).

| Element | Role |
|---|---|
| `load_protocol(path)` / `list_protocols(folder)` | Reads and validates a protocol file (`ProtocolError` with a readable message) |
| `Protocol` | A protocol: `build(kind, data, values)`, `build_query`, `build_response`, `decode(frame, kind)`, `matches(frame, kind)`, `crc_bytes`, `spec` / `has` / `max_value`; exposes `byte_order` (passed to `core.commands`) |
| `Decoded` | Decoded frame: `fields`, `errors`, `complete`, `extra`, `ok`, and by role `request_id`, `command_id`, `error`, `length`, `data`, `crc_ok` |
| `Crc`, `CRC_PRESETS` | 8 / 16 / 32-bit CRCs (width / poly / init / refin / refout / xorout model) and sums |
| `color_segments(decoded)` | Field colours (configuration file), used by `ui/hexview.py` |
| `DEFAULT_PROTOCOL`, `build_query`, `decode`… | Built-in generic protocol and shortcut functions (scripts, tests) |

### `commands/`

Library of the protocol commands, read from the `"commands"` and `"errors"` keys of the `Msg_*.json`.

| Element | Role |
|---|---|
| `load_library(folder, protocol_name)` | Commands + error codes of every file; `Library.problems` lists the invalid definitions, `Library.skipped` the files written for another protocol (`"protocol"` key) |
| `Library.by_id(id)` / `error_text(code)` | Command from its COMMAND ID / text of an error code |
| `encode_field(s)(...)` | Physical values → bytes (factor, offset, bounds, byte order) |
| `decode_fields(defs, data, cfg)` | Bytes → fields with physical value, unit, range check |
| `describe(decoded, cmd, lib)` | One-line summary with command name and error text |

### `trace/`

| Element | Role |
|---|---|
| `TraceRecorder` | Records each TX / RX frame on the fly (CSV) |
| `load_trace` / `save_trace` | Reading / writing a complete file |
| `exchanges`, `analyze`, `replay_delays` | Exchanges, timing statistics, replay delays |
| `compare`, `judge_exchange` | Bytes concerned, verdict with timeout |
| `TraceDocument` | Trace opened in the Replay panel: `set_cell` (validation), `insert_after` (time in the middle of the interval, or "Fixed delay" after the line above with the next lines shifted), `replace`, `move`, `delete`, `gaps`, `save_as_name` (renaming, `FileExistsError` if the name is taken) |

### `serial_link.py`

| Element | Role |
|---|---|
| `list_serial_ports(usb_ids, hide_bluetooth)` | Present ports, sorted (COM3 before COM10), filtered by VID / PID (`core/port_filter.py`), Bluetooth hidden |
| `check_port(device)` | Tests opening: `libre` (free), `occupé` (busy), `absent` (missing) or `erreur` (error) |
| `SerialLink.connect(...)` | Opens the port; raises `ConnectionError` with a readable message |
| `SerialLink.reconfigure(...)` | Changes speed / format without closing the port |
| `SerialLink.write(data)` | Sends bytes, counts the TX bytes |
| `SerialLink.set_lines(dtr, rts)` | Drives the DTR / RTS lines |
| `SerialLink.events` | Event queue: `("rx", bytes)` or `("lost", message)` |

Reading runs in a dedicated **thread**. Received bytes are grouped into one frame as long as the silence between two bytes stays below `gap_ms`, or up to the `frame_end` delimiter if it is set (Modbus ASCII): see `framing.py`. Events are put into a `queue.Queue`; the interface pops them every 30 ms from its own thread, because Tkinter does not accept being called from another thread.

On opening, DTR and RTS are left inactive so as not to reset an Arduino / ESP32 board. On Linux and macOS, the port is opened in exclusive mode to detect that it is already in use; on Windows this is the default behaviour.

### `tcp_link.py`, `link_switch.py`

`TcpLink` has the same interface as `SerialLink` (`connect(host, port)`, `write`, `events`, `gap_ms`, `frame_end`); `reconfigure` and `set_lines` have no effect. `LinkSwitch` holds both links and forwards everything to the active one (`mode` = `"serial"` or `"tcp"`, `link` setting): the application and the Link panel only see one object.

### `jsonc.py`

`load_file(path)` / `loads(text)`: JSON with `//` and `/* */` comments, replaced by spaces before reading (error line numbers stay correct). Used for the protocol files and the `Msg_*.json`; same function in TypeScript (`parseJsonc`).

### Interface language (`ui/i18n.py`)

The code is written in French; each displayed text goes through `_()` (`_("Envoyer")`, `_("Connecté : {0}").format(...)`), translated from `ui/lang/en.json`. Messages built by `core/` (decoding, link errors, file loading) go through `tr()`, which translates them from patterns (regular expressions) of the same file. The language is chosen at start by `serialhex.py`, before the panels are imported; changing the language restarts the program. `tests/test_i18n.py` checks that every text of `ui/` has a translation.

### `settings.py`
`Settings` is a dictionary saved in `settings.json`: last port, speed, format, end-of-frame delay, auto-connect, chosen protocol, colours, language, added message files (`message_files`), window size and separator positions.

## `ui/` modules

| File | Class | Receives | Role |
|---|---|---|---|
| `app/` | `App` | — | Creates the panels, holds the message list and the parameter values, does the sending, pops the serial events, shows / hides the Replay panel |
| `com_panel.py` | `ComPanel` | `link`, `settings`, `log`, `on_change` | Port choice, settings, connection, port monitoring |
| `messages_panel.py` | `MessagesPanel` | `on_select`, `on_send`, `on_send_selection`, `on_reload`, `on_load_files`, `on_remove` | Tree of the messages by group |
| `params_panel.py` | `ParamsPanel` | `on_send`, `on_to_replay`, `build` | Form, frame preview, periodic sending, "→ Replay" arrow (Manual tab, right of the messages) |
| `protocol/` | `ProtocolPanel` | `settings`, `on_send`, `on_protocol`, `on_to_replay`, `on_save` | Protocol tab: choice of the protocol, request from the library, decoding of the responses (auto / manual type). Receives the protocol through `set_protocol`, the library through `set_library`, each send through `on_sent`, each reception through `on_received` |
| `replay/` | `ReplayPanel` | `send`, `is_connected`, `traces_dir`, `log`, `describe`, `style`, `on_decode` | Replay panel: editable trace, renaming, row detail, replay with comparison. Receives each reception through `on_received`, the frames of the arrows through `put_frame` |
| `monitor_panel.py` | `MonitorPanel` | `on_gap_change`, `on_send_hex`, `crc_bytes`, `annotate` | Time-stamped log, protocol decoding, free hex with the protocol's CRC |

## Adding a feature

- **A new parameter type**: `encode_param` in `core/frames.py`, and the matching widget in `ParamsPanel._add_field`.
- **A new checksum**: `checksum` in `core/frames.py` (free messages); for the protocol, a CRC is described in the file of `protocols/` without touching the code.
- **A new protocol**: copy `protocols/exemple_generique.json`, describe the fields; it appears in the list of the Protocol tab.
- **A new panel**: create `ui/my_panel.py` (or a package `ui/my_panel/`) with its callbacks, then instantiate it and place it in `App._build` (`ui/app/window.py`).
