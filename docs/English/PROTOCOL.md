# Request / response protocol

[← Back to the README](../../README.md)

SerialHex can build and decode the frames of a request / response protocol. The **frame structure** (fields, sizes, CRC, colours) is not hard-coded: it is described in a **protocol file** of the `protocols/` folder. The device's **commands** are described in JSON files (`Msg_*.json`), with a **TX** part (what is sent) and an **RX** part (what is received).

| File | Role |
|---|---|
| `protocols/*.json` | Frame structure, one file per protocol ([CONF_PROTOCOL.md](CONF_PROTOCOL.md), quick reference `protocols/README_CONF.txt`) |
| `core/protocol/` | Engine: reads the protocol file, builds, decodes, checks the CRCs |
| `core/commands/` | Command library (TX / RX), error codes, units and conversions |
| `ui/protocol/` | **Protocol** tab |
| `msgLibrary/msgList/…/Msg_*.json` | Commands and error codes; folder given by the `"commands"` key of the protocol file |

## Protocol file (`protocols/`)

One file per protocol. It describes, field by field, the **request** frame (`tx`) and the **response** frame (`rx`): size of each field (in bytes or in bits), role (fixed byte, REQUEST ID, COMMAND ID, length, error code, CRC, DATA, free field, unread bytes, copied field), 8 / 16 / 32-bit CRC over the wanted byte range, several frame formats, ASCII encoding, colours and readable texts. The protocol in use is chosen at the top of the **Protocol** tab; the choice is remembered. **Reload** (Manual tab) also reads the file again after a change.

**Every option, with descriptions and examples: [CONF_PROTOCOL.md](CONF_PROTOCOL.md).**

Without a usable file, SerialHex uses a **built-in generic protocol** (`SYNC A5 5A | SEQ | CMD | LEN | CRC8 | DATA | CRC16`, see `core/protocol/default.py`).

## Command library (JSON)

Commands are described in the `Msg_*.json` files of the folder given by `"commands"` in the protocol file, under the `"commands"` key. The same file can contain `"messages"` (free frames, see [MESSAGES.md](MESSAGES.md)), `"commands"` and `"errors"`.

### File organisation

- One file per device, per function or per command: every `Msg_*.json` of the folder is read, in alphabetical order.
- Without a `"group"` key in the file, the group (category) is the end of the name: `Msg_Measures.json` → `Measures`.
- Shipped with the Techmelec version: `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json` (every standard Modbus function, generic, for any device) and `msgLibrary/msgList/modbus/Msg_Regulateur_Exemple.json` (fictitious temperature controller).
- A specific command (with `"match"`) and a generic command (without `"match"`) may share a COMMAND ID: when decoding, the specific one comes first, the generic one is the fallback (e.g. function 03: "Read setpoint and mode" for register 0x0000, "03 Read holding registers" for the others).

### File structure

Extract of `msgLibrary/msgList/modbus/Msg_Regulateur_Exemple.json`:

```jsonc
{
  "protocol": ["Modbus RTU", "Modbus ASCII", "Modbus TCP"],   // target protocols
  "group": "READ",
  "commands": [
    {
      "name": "Écrire consigne",
      "name_en": "Write setpoint",
      "id": "0x06",                                  // Modbus function = COMMAND ID
      "group": "WRITE",
      "description": "Registre 0x0000 ; la réponse est l'écho de la requête",
      "match": {"register": "0x0000"},               // tells it apart from the other 06 commands
      "tx": [
        {"name": "register", "label": "Registre", "type": "uint16", "default": "0x0000", "min": 0, "max": 0},
        {"name": "setpoint", "label": "Consigne", "type": "int16", "factor": 0.1, "unit": "°C",
         "min": -50, "max": 150, "default": 23}
      ],
      "rx": [
        {"name": "register", "label": "Registre", "type": "uint16"},
        {"name": "setpoint", "label": "Consigne", "type": "int16", "factor": 0.1, "unit": "°C"}
      ],
      "presets": [
        {"name": "20 °C", "values": {"setpoint": 20}}
      ]
    }
  ]
}
```

With `setpoint = 37.5`, the request is `01 06 00 00 01 77 C8 7C` (375 as big-endian int16).

`Msg_*.json` files accept `//` and `/* */` comments, like protocol files. A key set to `null` counts as missing: each field can be written with **all its parameters**, leaving the unused ones at `null`.

`"protocol"` tells which protocol the file was written for (name, or list of names). The commands of a file written for another protocol are skipped, with a message in the monitor; without this key, the file suits every protocol. Details: [CONF_PROTOCOL.md §12](CONF_PROTOCOL.md#12-link-with-the-command-files).

### A command

| Key | Required | Role |
|---|---|---|
| `name` | yes | Displayed name |
| `id` | yes | COMMAND ID (`"0x06"`, `"0x80000004"` or a number); unique, except for commands told apart by `match`, `header` or `variant` |
| `presets` | no | Predefined data offered in the "Data" menu |
| `description` | no | Text shown under the command |
| `tx` | no | DATA fields of the **request**, in order; empty = no data sent |
| `rx` | no | DATA fields of the **response**, in order; empty = no data expected |
| `group` | no | Group (category); default: the file's. Readable text in `categories` of the protocol file |
| `name_en` / `description_en` | no | Name and description in English (English interface) |
| `variant` | no | Request frame format, for a protocol with variants (M-Bus `"Courte"` / `"Longue"`, PROFIBUS `"SD1"`…) |
| `header` | no | Values of header fields specific to the command, by name or role: `{"CI": "0x52"}`. Two commands with the same COMMAND ID can be told apart this way |
| `match` | no | Values of `tx` fields that tell apart commands with the same COMMAND ID (Modbus: same function 03, different registers): `{"register": "0x0010"}`. The field takes this value by default |
| `attributes` | no | Free fields shown after the description: `{"access": "R", "level": "expert"}` |
| `hidden` | no | `true`: **hidden** command, see below |

A COMMAND ID can only be used once, unless the commands are told apart by `match`, `header` or `variant`, or one of them is hidden. The response is decoded with the command of the request sent with the same REQUEST ID (Protocol tab: the chosen command; frame from elsewhere: found from the COMMAND ID and `match` / `header`).

### Hidden commands (`hidden`)

A command with `"hidden": true` does not appear in the "Command" and "Response type" lists of the Protocol tab, but it is still **recognised when decoding**: a frame using it is summarised with its name in the monitor. Useful for obsolete, internal or commented-out commands of the device code, which you want to identify without cluttering the lists.

- The **"Hidden (n)"** checkbox, to the right of the command list, adds them to the lists (choice remembered; the checkbox only appears if there are hidden commands).
- `"hidden": true` at file level hides all its commands; a command can opt out with `"hidden": false`.
- A hidden command can have the same COMMAND ID as a visible one (old name of a reused command): the visible one wins when decoding.
- The monitor shows at load time: `Protocol: 1000 hidden command(s), visible with the "Hidden" checkbox`.

```json
{"name": "Old measurement", "id": "0x000C", "hidden": true, "attributes": {"state": "obsolete"}}
```

### A field (in `tx` or `rx`)

| Key | Role | `null` / missing |
|---|---|---|
| `name` | Field name (unique in the list) | required |
| `label` | Displayed label, if different from `name` | `name` |
| `label_en` | Label in English (English interface) | `label` |
| `type` | Data format, see the table below | `uint8` |
| `count` | Array size: `U8[4]` → `"type": "uint8", "count": 4` | 1 (not an array) |
| `unit` | Displayed unit: `"%"`, `"°C"`, `"mW"`… | none |
| `factor` | Conversion factor | 1 |
| `offset` | Offset | 0 |
| `min` / `max` | Allowed range, **in real units**; checked when sending, shown in red when decoding | **type limits**, computed automatically |
| `default` | Default value, in real units (request) | 0, or the first choice |
| `decimals` | Number of decimals shown | deduced from `factor` and `offset` |
| `format` | Input / display of an array: `"ip"` (`192.168.1.10`) or `"mac"` (`00:1A:2B:3C:4D:5E`) | values separated by commas |
| `choices` | List of choices `{ "label": value }` on an integer: drop-down menu. Value in decimal or as a hex string (`"0xFF00"`) | free input |
| `bits` | Bit field `{ "bit number": "name" }`: the bits set are listed by name | plain integer |
| `length` | `ascii` / `hex`: fixed size in bytes; `bcd`: number of bytes | variable size; 4 for `bcd` |

**Conversion**: `real value = raw value × factor + offset`.

| Example | Input | Raw value sent |
|---|---|---|
| `uint16`, `factor: 0.1`, unit mW | `12.5` | 125 |
| `int16`, `factor: 0.01`, unit °C | `-5.25` | -525 |
| `uint16`, `factor: 0.001`, `offset: 2.5`, unit V | `3.3` | 800 |

Decimal values accept a dot or a comma (`12,5`). The raw value is rounded to the nearest integer.

### Automatic min / max

If `min` or `max` is `null`, the limit is **computed from the type**, then converted to real units with the factor and offset:

| Type | `factor` / `offset` | Automatic range |
|---|---|---|
| `uint8` | — | 0 to 255 |
| `int16` | — | -32768 to 32767 |
| `uint8` | `factor: 0.1` | 0.0 to 25.5 |
| `uint16` | `factor: 0.001`, `offset: 2.5` | 2.500 to 68.035 |
| `float`, choices, bits, text | — | no automatic limit |

In the Protocol tab, the **Description** column of the table shows the range applied, always in real units (from the JSON, or computed from the type). A value outside the type is refused with a message in real units: `30 outside the limits of type uint8 (0.0 mW to 25.5 mW)`.

### Field types (data format)

| Type | Also accepted | Size | Note |
|---|---|---|---|
| `uint8`, `int8` | `u8`, `i8`, `U8` | 1 | unsigned / signed integer |
| `uint16`, `int16` | `u16`, `i16` | 2 | protocol order (`byte_order`) |
| `uint32`, `int32` | `u32`, `i32` | 4 | protocol order: `0x12345678` → `12 34 56 78` |
| `uint16be`, `int32le`… | `u16be`, `i32le`… | 2 / 4 | byte order forced for this field |
| `float` | `f32`, `float32`, `F32` | 4 | IEEE 754 float |
| `bool` | | 1 | checkbox, 0 / 1 |
| `ascii` | | `length`, or variable | text; padded with `00` if `length` |
| `raw` | `hex`, `RAW` | `count` (or `RAW[n]`), or variable | **raw bytes, no conversion**: entered and shown in hex |
| `bcd` | | `length` (4 by default) | decimal digits, 2 per byte (M-Bus identification number: `12345678` → `78 56 34 12` in little endian); `factor` / `unit` possible; a digit > 9 is shown "invalid BCD" |
| `enum` | | depends on `size` | old way of writing a choice; prefer an integer with `choices` |

Upper case is accepted, and the array size can also be written in the type, as in datasheets: `"type": "U8[4]"` is the same as `"type": "uint8", "count": 4`. A variable-size field (`ascii` / `hex` without `length`) is only allowed **last**.

### Arrays

| Datasheet | JSON | Input / display |
|---|---|---|
| `U8[4]` (IP address) | `{ "type": "uint8", "count": 4, "format": "ip" }` | `192.168.1.100` |
| `U8[6]` (MAC address) | `{ "type": "uint8", "count": 6, "format": "mac" }` | `00:1A:2B:3C:4D:5E` |
| `F32[2]` | `{ "type": "float", "count": 2, "unit": "mm" }` | `-1000, 2500.5` → `[-1000, 2500.5] mm` |
| `U32[2]` + bits | `{ "type": "uint32", "count": 2, "bits": { ... } }` | list of the bits set |

Without `format`, values are separated by commas, spaces or semicolons.

### Raw bytes (raw)

For data without conversion (no factor, unit or choices), use `raw`: the value is entered and shown directly in hex.

| JSON | Input | Note |
|---|---|---|
| `{ "name": "data", "type": "raw", "count": 4 }` | `01 02 03 04` | exactly 4 bytes; default `00 00 00 00` |
| `{ "name": "data", "type": "RAW[4]" }` | `01 02 03 04` | the same, datasheet notation |
| `{ "name": "data", "type": "raw" }` | `01 02 03 …` | any number of bytes: **last** field only |

For `raw`, `count` is the **number of bytes** (not an array). Several fixed-size `raw` fields can follow each other.

### Bit field

An integer (or an array of integers) with `"bits"` is decoded as the list of the bits set. For an array, word 0 holds bits 0 to 31, word 1 bits 32 to 63, etc. Example, alarm word over 2 × 32 bits:

```json
{ "name": "alarms", "type": "uint32", "count": 2,
  "bits": { "0": "Internal fault", "1": "Door open", "32": "Temperature out of range" } }
```

Display: `0x0000000100000003 : Internal fault, Door open, Temperature out of range`, in red as soon as a bit is set; a bit set without a name is shown `bit N`.

### Predefined data

A command can offer sets of values, chosen in the **Data** menu of the tab:

```json
"presets": [
  { "name": "On",  "values": { "state": "on" } },
  { "name": "Off", "values": { "state": "off" } }
]
```

Fields missing from a preset keep their default value. After a preset is chosen, the fields can still be edited by hand (the menu then goes back to "typed by hand"). Each preset is checked at load time.

### Error codes

`"errors"` key, in any `Msg_*.json` file, or in the protocol file (which wins). A text can be bilingual: `"4": {"fr": "Commande inconnue", "en": "Unknown command"}`.

```json
{
  "errors": {
    "0": "OK",
    "4": "Unknown command",
    "6": "Parameter out of range"
  }
}
```

Codes can also be written in hex (`"0x04"`). The text is shown next to the error code (field with role `error`) in the decoding and in the monitor.

### Checks at load time

An invalid definition is reported in the monitor (and the command skipped): unknown type, `factor` at 0, `choices` missing, duplicated field, variable size elsewhere than last, default value out of range, duplicated COMMAND ID.

## Protocol tab

### Request (TX)

The upper part of the tab (no title) prepares the request:

1. **TX CMD**: choose a command from the library (`WRITE / Write setpoint (0x06)`), or "manual entry". **You can type in the list to search**: a click in the field selects all the text, you type directly, and the **suggestions open under the field** from the first letter (name, category or COMMAND ID: `setpoint`, `READ`, `0x1E` finds the Get `0x0000001E` and the Set `0x8000001E`); ↑ / ↓ to move in them, Enter or a click to choose; field emptied or Esc: the current command comes back. **Favourites**: the **☆** button to the right of the list adds the current command to the favourites (**★**: removes it); if there is at least one, the **Favourites** list appears under TX CMD (3 visible rows, scrolling beyond) and a click there chooses the command. Favourites are remembered per protocol (`settings.json`, `favorite_commands`). For a **Get** (bit 31 of the COMMAND ID at 0), a **Send** button also appears to the right of the COMMAND ID, just under the list (same action as the Send button at the bottom). The lists are sorted by **opcode**: COMMAND ID in ascending order over its 31 least significant bits, the Get (bit 31 at 0) before the Set (bit 31 at 1), whatever the file or the name. For a protocol with several frame formats, the **Format** list chooses the variant. The **Hidden (n)** checkbox adds the `"hidden"` commands to the list ([see above](#hidden-commands-hidden)).
2. **Data**: if the command has predefined data, choose one in the menu; otherwise, or afterwards, edit the values **in the frame table**.
3. With a command: COMMAND ID is filled in, and each `tx` field appears **in blue** under the DATA row of the table. **Click the Value column** (or double-click the row, or Enter): the value is edited in place; Enter or a click elsewhere confirms, **Tab** goes to the next field, Esc cancels. A field with choices (or a boolean) offers a list. The **Description** column recalls the type and conversion, the range in real units (from the JSON, or from the type) and the default value. An invalid value stays displayed in red with "invalid: …", the error message replaces the hex frame and sending is blocked.
   The **DATA** row (in blue) is edited the same way, as **raw hex** (`FF 33 33 53 70 61 72 6B`): the frame uses these bytes as they are and the fields show their decoding. A field changed afterwards replaces its bytes in the raw DATA (if it keeps the same size; otherwise back to the field values). DATA cleared, or predefined data chosen: back to the field values. In manual entry, the DATA row and the Data field go together.
   **Raw or converted value**: a field can also be edited in its **Hex** column, as raw bytes (same size; `00 00 00 40` for a float32 of 2.0): DATA then becomes raw DATA and the fields show its decoding. Bounds (min / max) and type are shown in the Description column. The request and response tables take the height of their rows (whole frame visible) and the divider places itself; the hex frame uses the full width (on several lines if needed), with the buttons just below.
4. In manual entry: COMMAND ID in hex, and DATA in hex on the **Data** line.
5. The **complete frame** is detailed below, field by field (the DATA fields appear under the DATA row, with their physical value).
6. **Save…** asks for a name (the suggested file `Msg_<name>.json` is shown live), then opens the file browser with this file pre-filled in `msgLibrary/msgManual/`, still editable, and saves the request (REQUEST ID, COMMAND ID, DATA, raw or from the fields) as a message of the Manual tab; name already used in the file: replace, keep both or cancel. It can then be sent again in one click, changing the DATA if needed ([protocol message](MESSAGES.md#protocol-message-request)). **Copy** puts the hex frame on the clipboard; **Send** sends it (greyed out while the link is not connected); **→ Replay** puts it into the selected row of the trace in the Replay panel (inserted after, or instead, see [TRACE.md](TRACE.md)).
7. **REQUEST ID** is shown and entered in hex (`0x05`, over the field size; decimal is also accepted). With the **REQ+** checkbox (tooltip "auto req_id"), it is incremented after each successful send (0xFF → 0x00 on 1 byte). The monitor summaries write it the same way: `request #0x05`.

The REQUEST ID and COMMAND ID labels take the names from the protocol file; a field missing from the protocol (size 0) is greyed out.

The values entered are kept for each command when switching from one to another.

### Response (RX)

- With **"Follow received responses"**, each received frame is decoded automatically. A frame can also be pasted and decoded with **Decode** (choose Request or Response).
- **Response type**:
  - **Auto**: SerialHex remembers the COMMAND ID of each request sent (from the tab, the message list or free hex) with its REQUEST ID; on reception, the response is decoded with the `rx` part of this command.
  - **A command** chosen in the list: forces decoding with its `rx` part.
  - **Raw**: DATA shown without decoding.
- The table shows the header, the error code with its text (green if 0, red otherwise), and each DATA field with its physical value (unit included) and its raw value.
- DATA **without definition** (unknown command, no `rx` field, or raw-byte field): the possible readings are added, for 1 to 8 bytes: integer (`DC 05` = `1500 (0x05DC)`, protocol byte order), signed integer if the most significant bit is set, 4-byte float when plausible (`00 00 96 42` = `float 75`).
- The summary tells which command was used and how it was found: `[type: Read temperature, auto]`.
- Reported in red: wrong CRC, truncated frame, extra bytes, DATA shorter than expected or not described, value out of range, error code ≠ 0.

### Monitor

With **"Decode protocol"**, each protocol frame is summarised; at the end of the line, in bold (blue for TX, purple for RX), the **converted value** of each DATA field (type, factor, offset, unit, choices, bits from the JSON), up to 8 fields separated by `|`:

```
TX  01 03 00 00 00 02 C4 0B      "request #0x01 · Read setpoint and mode · 4 B · CRC OK"   => Register = 0  |  Count = 2
RX  01 03 04 00 E6 00 01 DA 04   "response #0x01 · Read setpoint and mode · 5 B · CRC OK"   => Byte count = 4  |  Setpoint = 23.0 °C  |  Mode = auto (1)
TX  01 06 00 00 01 77 C8 7C      "request #0x01 · Write setpoint · 4 B · CRC OK"   => Register = 0  |  Setpoint = 37.5 °C
RX  01 04 04 00 D7 01 F4 4B AB   "response #0x01 · Read measurements · 5 B · CRC OK"   => Byte count = 4  |  Temperature = 21.5 °C  |  Humidity = 50.0 %RH
RX  01 83 02 C0 F1               "response #0x01 · Read setpoint and mode · error 2 (Illegal data address) · CRC OK"
```

- The value is in **red** if it is outside min / max, or if a bit of a `bits` field is set (`=> Relay = 0x01 : alarm relay active`).
- The **error code** byte of a response has a **green** background at `00`, a **red** background for any other code; in the summary, `error N (text)` is then written in **red** (as is a wrong CRC or a truncated frame). The other bytes of the response keep their colours: it is the **request** that the device refused.
- A response in error shows no value: its DATA does not have the normal format.

### Free hex + CRC

- **"Auto CRC (crc16_modbus)"** checkbox: the main CRC of the protocol (the one of the first CRC field of the request, CRC16 Modbus for Modbus RTU) is computed over the bytes typed and appended to the frame when sending, in the protocol's byte order.
- Under the field, the **preview** shows the exact frame that will be sent, in colour:
  - checkbox ticked: bytes typed + computed CRC, its **bytes in red**;
  - checkbox unticked: the frame as typed or pasted;
  - as soon as it is a **complete** protocol frame: colours of the protocol file (header grey, COMMAND ID bold, CRC green if correct, red if wrong).

## Use in a script

```python
from core.commands import load_library, encode_fields, decode_fields, describe
from core.protocol import load_protocol, QUERY, RESPONSE

proto = load_protocol("protocols/modbus_rtu.json")
lib = load_library(proto.commands_dir, proto.name)          # "commands" folder of the file

cmd = lib.find(0x06, bytes.fromhex("00 00"), proto)          # Write setpoint (register 0)
data = encode_fields(cmd.tx, {"setpoint": 37.5}, proto)
frame = proto.build_query(request_id=1, command_id=cmd.id, data=data)    # 01 06 00 00 01 77 C8 7C
# other form: proto.build(QUERY, data, request_id=1, command_id=cmd.id)

get = lib.find(0x03, bytes.fromhex("00 00 00 02"), proto)    # Read setpoint and mode
d = proto.decode(response, RESPONSE)
print(describe(d, get, lib))             # response #0x01 · Read setpoint and mode · 5 B · CRC OK
print(d.request_id, d.error, d.ok)       # fields found by their role, whatever their name
fields, problems = decode_fields(get.rx, d.data.raw, proto)
for f in fields:
    print(f.name, f.text)                # Setpoint 23.0 °C …
```

Same engine in TypeScript for the React GUI: `parseProtocol()` in the `js/` package (see [INTERFACE.md](INTERFACE.md)).

Tests: `tests/test_protocol.py`, `tests/test_protocol_vectors.py`, `tests/test_commands.py`. The vectors `tests/protocol_vectors.json` (generated by `tools/gen_protocol_vectors.py`) are checked byte for byte by Python and by TypeScript (`js/test/protocol.test.ts`).
