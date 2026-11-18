# User interface

[← Back to the README](../../README.md)

```
┌──────────────────────── Link (serial / TCP) ──────────────────────┐
├─ [Protocol] [Manual] ─ [Language] [Colours…] [x] ▶ Replay ─┬─ Replay ─┤
│  Protocol: request / response  ·  Manual: messages  │  (checkbox) │
├───────────────────────────── Monitor ─────────────────────────────┤
```

| Area | Contents |
|---|---|
| **Manual** tab | On the left, the list of JSON messages (Reload, Load…, Remove, Delay, Send selection); on the right, the parameters of the selected message |
| **Protocol** tab | Requests of the chosen protocol (the one from `edition.json` on first start) and decoding of the responses, see [PROTOCOL.md](PROTOCOL.md) |
| **Replay** panel | Show, edit, save and replay a CSV trace, see [TRACE.md](TRACE.md) |

### Language

The **Français / English** list, to the right of the tab row, chooses the interface language. The choice is remembered (`settings.json`, key `language`) and SerialHex offers to restart to apply it. In English:

- every label, button and monitor message is translated (file `ui/lang/en.json`, editable: a missing text stays in French);
- engine messages (wrong CRC, truncated frame, port busy…) are translated from patterns in the same file;
- texts of the protocol and command files switch to English when they exist: `description_en`, `values` / `errors` / `categories` written `{"fr": …, "en": …}`, `name_en`, `description_en`, `label_en` of the commands.

### Replay

The **▶ Replay** checkbox, to the right of the tab row, shows or hides the Replay panel: hidden, the tabs take the whole width; shown, it takes the right half of the window (movable separator). The **→ Replay** arrows of the Manual and Protocol tabs send the built frame into the selected row of the trace.

The separators between the areas can be moved with the mouse. The window size and the separator positions are **remembered** and restored at the next start (`settings.json`); the separator of each tab is placed the first time that tab is shown. On first start, the window is 1720 × 920, the upper area takes about 74 % of the height and the monitor 26 %; in the Protocol tab, the request takes two thirds; in the Manual tab, the message list takes about 30 % of the width (never less than 150 px). When a new version changes the default layout, the remembered size and separators are forgotten once (`layout_version`).

### Frame colour code

The same colour code is used in the Manual tab, the Protocol tab and the monitor:

| Colour | Bytes |
|---|---|
| light grey | Header: fixed bytes of a JSON message; protocol fields with `"color": "hdr"` (sync, address, REQUEST ID) |
| **bold** | Protocol fields with `"color": "cmd"` (COMMAND ID) |
| blue | DATA, in the previews of the Manual and Protocol tabs and in the DATA input fields (colour of the TX frames); in the monitor, DATA keeps the colour of the line |
| pastel green | Checksum of a JSON message; protocol fields with `"color": "crc"` (HEADER CRC and DATA CRC) |
| green / red background | Error code of a response: `00` (no error) on a green background, any other code on a red background |
| very light grey, struck through | Unread bytes (role `na`) |
| red | Failed check (wrong CRC, wrong fixed byte) |

For the protocol, each field chooses its colour category in the protocol file (`"color": "hdr"`…), or an exact colour (`"color": "#FF8800"`); colours only apply to a **complete** frame. All these colours can be set with the **Colours…** button (below).

### Colours

**Colours…** button, to the right of the tab row (next to "▶ Replay"): settings page for every colour of the interface.

| Group | Colours |
|---|---|
| Monitor and replay | Sent frames (TX, blue), received frames (RX, purple), information (grey), errors (red); the TX / RX rows of the replay table follow |
| Frame fields | Header `hdr`, command `cmd` (empty = colour of the line, in bold), CRC `crc`, unread bytes `na`, wrong CRC or fixed byte, backgrounds of a zero and a non-zero error code |

For each colour:
- a **sample** of the chosen colour (clicking it opens the palette);
- the **hex** code (`#1F5FBF`, or `1F5FBF`), editable with the keyboard; it stays red while it is not valid;
- **Palette…**: the system colour picker;
- **Default**: the original colour.

The **preview** at the bottom shows typical frames (request, correct response, error response with a wrong CRC, unread bytes, information) with the colours being set. **Apply** updates the whole interface, including lines already shown; **OK** applies and closes; **All defaults** restores the original colours. Colours are remembered in `settings.json`. On an error-code background, the text automatically turns black or white to stay readable.

## Link

The panel fits on **two lines**:

```
Link (•) Serial ( ) TCP   Port [COM3 — USB Serial Port ▾] [Refresh] [x] FTDI ● free   [Connect] ● Disconnected
Baud rate [115200] Data [8] Parity [None] Stop [1] Flow [None]      DTR RTS  Auto-connect…  TX 0 B RX 0 B
```

In TCP, line 1 shows the server address and port instead of the serial port, and line 2 no longer has the serial port settings.

| Element | Role |
|---|---|
| **Link** | **Serial** (COM port) or **TCP** (Modbus TCP, serial / Ethernet gateway). Choice remembered; cannot be changed while connected |
| **Address / Port** (TCP) | Server to reach, for example `192.168.1.10` and `502` (Modbus TCP); remembered on connection |
| **Port** | Ports present on the machine, with their description (e.g. `COM3 — USB-SERIAL CH340`) |
| **Port state** | Indicator next to the port: **free**, **busy** (used by another program), **missing** |
| **Refresh** | Reads the port list again and re-tests the selected port |
| **FTDI** | Only shows the adapters of the `"filter"` list of `edition.json` (FTDI by default: VID `0x0403`, PID `6001` FT232R, `6010` FT2232, `6011` FT4232, `6014` FT232H, `6015` FT-X). Choice remembered; state on first start: `"filter_default"`. See [Port list](#port-list-editionjson) |
| **Baud rate** | Chosen from the list or typed (confirm with Enter) |
| **Data / Parity / Stop / Flow** | Line format, 8N1 without flow control by default |
| **Connect / Disconnect** | Right after the port state. Opens / closes the port; an indicator (bigger and green once connected) and the text show the state (`Connected — COM3 @ 115200 8N1`) |
| **DTR / RTS** | Manual control of the control lines once connected |
| **TX / RX** | Number of bytes sent / received since the connection |
| **Auto-connect at startup** | Reconnects automatically to the last port used at the next start |

### Port list (`edition.json`)

The `"ports"` key of `edition.json` sets the serial port list:

```jsonc
"ports": {
  "hide_bluetooth": true,       // serial ports over Bluetooth never shown
  "filter_label": "FTDI",       // text of the filter checkbox
  "filter_default": true,       // checkbox ticked on first start (remembered afterwards)
  "filter": [                   // adapters kept when the checkbox is ticked
    {"name": "FT232R / FT245R", "vid": "0x0403", "pid": "0x6001", "enabled": true},
    {"name": "CH340",           "vid": "0x1A86", "pid": "0x7523", "enabled": false}
  ]
}
```

- `"enabled": false` removes an adapter from the filter without deleting its line; for another adapter, add a line with its VID and PID (shown in the Device Manager: `USB\VID_0403&PID_6001`).
- **Bluetooth** ports (Windows: "Standard Serial over Bluetooth link", `BTHENUM`; Linux: `/dev/rfcomm*`; macOS: `/dev/cu.Bluetooth*`) are removed from the list, whether the checkbox is ticked or not, if `"hide_bluetooth"` is `true` (default value).
- Key missing: Bluetooth hidden, FTDI filter unticked.

- The port list updates by itself when an adapter is plugged in or unplugged.
- Settings changed while connected are **applied immediately** to the port, without disconnecting.
- If the cable is pulled out or the port fails, the disconnection is detected and reported in the monitor.
- The port is opened **without asserting DTR or RTS**: an Arduino / ESP32 board does not reset on connection.
- In **TCP**, received bytes are split into frames as on a serial port (silence "End of frame after … ms"); DTR / RTS and the format settings do not apply. The device closing the connection is reported as a lost link.
- Protocol with an **end of frame** (Modbus ASCII: CR LF): each received frame is cut as soon as its delimiter arrives, without waiting for the silence.
- The last settings are remembered in `settings.json` and reloaded at start. The **last port** used (connected or just chosen in the list) is selected again; the monitor shows "Last port used: COM3", or that it is missing.

## Manual tab

### Messages (left)

- Messages are sorted by group, one group per `msgLibrary/msgManual/Msg_<function>.json` file (see [MESSAGES.md](MESSAGES.md)).
- **Click**: shows the parameters of the message.
- **Double-click**: sends the message.
- **Ctrl / Shift + click**: multiple selection. **Send selection** sends the messages in order, separated by the given delay (ms).
- **Reload**: reads the `msgLibrary/msgManual/` folder and the added files again after the files were changed.
- The list only contains the messages present in the files: put the most useful frames there, ready to send, to save time. Protocol commands are chosen in the Protocol tab.
- A **protocol message** (saved with the **Save…** button of the Protocol tab, or written with the `request` key) shows REQUEST ID, COMMAND ID and DATA, all **editable**: the frame is rebuilt by the current protocol, length (DATA LENGTH) and CRC included. DATA is written in blue, and its number of bytes is shown live on the right (`hex · 9 byte(s) → DATA LENGTH = 9`). See [MESSAGES.md](MESSAGES.md#protocol-message-request).
- **Converted value** (protocol message): under DATA, the **Value** section shows DATA converted according to the command of the current protocol that has this COMMAND ID. One field per value: drop-down list for a choice (`off` / `on`), number in real units, IP, text… The command's **predefined data** are offered next to it. Both directions are synchronised live: changing DATA updates the values, changing a value recomputes DATA over the right number of bytes. Fields **in green**: known conversion. **In blue**: no conversion (unknown COMMAND ID, or command without described DATA); DATA is then read as an unsigned integer (protocol byte order), and a value entered is written back over the number of DATA bytes (more if it does not fit). The **Hex** checkbox shows integers in hex (`0x05DC`) instead of decimal (default). An invalid value, or DATA of the wrong size, is reported in red on the right.
- **Load…**: adds JSON files stored elsewhere. **Duplicates**: a file already loaded is not read again, a message identical to one already present (a copy of a file under another name…) is skipped; two messages with the same name in the same group but different contents are both kept, the name of the source file in brackets tells them apart (`Read state  [Msg_Bench.json]`). The list of added files is **remembered** (`settings.json`, `message_files`): they stay shown after a save, **Reload** or at the next start; **Remove** takes the added files of the selected messages out of the list (nothing is deleted from the disk; the files of `msgLibrary/msgManual/` are always shown).
- While the link is not connected, **Send**, **Repeat every** and **Send selection** are greyed out (like Send in the Protocol tab and the monitor's **Free hex**).

### Parameters (right)

- Under the description: "Written for: Modbus RTU", the protocol the message file was written for (`"protocol"` key), in orange if it differs from the current protocol.
- **→ Replay**: the frame of the message, with the values entered, goes into the selected row of the replay.

- A form is generated for the selected message: text field, drop-down list or checkbox depending on the type.
- Integers accept decimal (`12`), hex (`0x0C`) or binary (`0b1100`).
- The **frame** is recomputed on every change, checksum included, and shown in colour: fixed bytes in grey, checksum in green. An invalid or out-of-range value is shown in red.
- **Send**: sends the frame once.
- **Repeat every … ms**: periodic sending, stopped automatically on disconnection or when another message is selected.

## Protocol

Tab dedicated to the request / response protocol of the device:

- **Protocol**: list of the files of the `protocols/` folder (`Modbus RTU (modbus_rtu.json)`), with their description next to it. The choice is remembered; it changes the frame structure (fields, sizes, CRC, colours) everywhere: tab, monitor, free hex, timeout. An invalid file is reported in the monitor and marked ⚠ in the list. Format: [PROTOCOL.md](PROTOCOL.md#protocol-file-protocols).

- **Request** (upper part, **TX CMD**): choose a command from the library (type in the list to search, suggestions open; ☆ adds to the **Favourites**, shown under TX CMD; a Get also has a **Send** button to the right of the COMMAND ID); its DATA fields appear in blue in the frame table, with their default value, and are **edited directly in the table** (click the Value column). For a protocol with several frame formats (M-Bus, PROFIBUS), the **Format** list chooses the variant; a command that specifies its own (`"variant"`) selects it by itself. The complete frame (length and CRC included) is detailed below. The **DATA** row (in blue) can be edited too, as **raw hex**: the fields then show the decoding of these bytes (a field changed afterwards changes its bytes in the raw DATA; DATA cleared or predefined data chosen: back to the field values). Buttons: **Save…** (asks for the message name, the suggested file `Msg_<name>.json` being shown live, then opens the file browser on `msgLibrary/msgManual/` with this file pre-filled, still editable; `Msg_` prefix added if needed; group "Sauvegardés"; a file outside `msgLibrary/msgManual/` is loaded anyway; name already used in the file: replace, keep both ("name (2)") or cancel; identical: nothing is written), **Copy** and **Send** (greyed out while the link is not connected). The **REQ+** checkbox (tooltip "auto req_id") increments the REQUEST ID after each send. Manual entry possible (COMMAND ID + DATA in hex).
- **Response (RX)**: each received (or pasted) frame is decoded: header, error code with its text, DATA fields in physical units. The **Value** column adds the meaning of the value (`values` of the file: `3 (0x03) Read Holding Registers`), the **Description** column the description of the field. The **response type** is found automatically from the REQUEST ID, or chosen by hand.
- **Byte order**: the one of the protocol file (`byte_order`).
- The request and response tables take all the remaining space (the request takes two thirds on first start). The separator between request and response can be moved with the mouse.

Details: [PROTOCOL.md](PROTOCOL.md).

## Monitor

| Element | Role |
|---|---|
| Log | `TX` in blue, `RX` in purple, information in grey, errors in red, time-stamped to the millisecond. DATA bytes keep the colour of the line; only the header, the COMMAND ID, the error code and the CRCs have their own colour. Lines are not wrapped: horizontal scroll bar at the bottom to see the end of long lines |
| **ASCII** | Shows the text version of each frame |
| **Show TX** | Hides the sent frames to see only what is received |
| **Auto scroll** | Follows the last lines |
| Colours | Header in grey, COMMAND ID in bold, CRC in green (see the colour code above) |
| **● Trace** | Records every TX / RX frame in a time-stamped CSV file; click again to stop. See [TRACE.md](TRACE.md) |
| **+ Replay** | Copies the monitor frames (TX and RX, with their times) into the Replay panel, as a new trace to replay; without frames, only shows the panel. See [TRACE.md](TRACE.md) |
| **Decode protocol** | Adds a summary to each frame of the chosen protocol (recognised by its fixed bytes, `A5 5A` for the generic protocol): "response #0x05 · error 0 · 2 B · CRC OK", then at the end of the line, in **bold** (colour of the line: blue for TX, purple for RX), the value of each DATA field converted according to the JSON (type, factor, offset, unit, choices, bits): `=> Setpoint = 23.0 °C`. In red if the value is outside min / max or if an error bit is set |
| **End of frame after … ms of silence** | Received bytes are grouped into a single frame as long as the silence between them is shorter than this delay |
| **Reply timeout … ms** | Maximum delay (500 ms by default, remembered) between a protocol request and its response, recognised by its REQUEST ID (protocol without REQUEST ID: not monitored). Without a response in time, a red line is shown: `TIMEOUT: no response in 500 ms to "Read setpoint and mode #0x03" (REQUEST ID 0x03)`. Also used by the replay |
| **Clear / Save…** | Empties the log / saves its frames as a replayable **CSV trace** (`.csv`, in `traces/` by default, to open in the Replay panel) or its text as `.txt` |
| **Free hex** | Sends the bytes typed (`AA 55 01 0D`, `AA55010D` or `0xAA,0x55`); greyed out while the link is not connected |
| **Auto CRC (crc16_modbus)** | Computes the main CRC of the chosen protocol (CRC16 Modbus for Modbus RTU) over the bytes typed and appends it to the frame when sending |
| Preview | Under the field: the exact frame that will be sent, in colour. Checkbox ticked: computed CRC (last bytes) in red; unticked: the frame as pasted. Complete protocol frame: header grey, COMMAND ID bold, CRC green (red if wrong) |

## Command-line terminal

For quick use without the interface:

```bash
python tools/hexterm.py           # lists the available ports
python tools/hexterm.py COM3      # 115200 baud by default
python tools/hexterm.py COM3 9600
```

Type the bytes (`AA 55 01 0D`) then Enter, `q` to quit.

## Troubleshooting

| Problem | Solution |
|---|---|
| Port shown as "busy" | Close Tera Term or the other program using it, then **Refresh** |
| No port in the list | Check the cable and the USB-serial driver (CH340, CP210x, FTDI…); untick the **FTDI** filter for another adapter |
| Message list empty in the Manual tab | Move the separator on the left edge of the tab; check the monitor ("… message(s) loaded from msgLibrary/msgManual/") |
| `No module named 'serial'` | `pip install -r requirements.txt` (the package is called `pyserial`, not `serial`) |
| `No module named 'tkinter'` | Linux: `sudo apt install python3-tk` |
| Access denied on Linux | `sudo usermod -aG dialout $USER`, then log in again |
| Nothing received | Check baud rate and format, crossed TX/RX wiring and common ground |
| Sending blocked with RTS/CTS | The device does not handle flow control: set **Flow** back to "None" |
| Received frames cut into pieces | Increase "End of frame after … ms of silence" |
| Request refused / inconsistent values | Check in the monitor that the HEADER CRC is green (complete frame and correct CRC) |
| Parity change refused | Some adapters do not accept every format on the fly: disconnect and reconnect |
