# Message files

[← Back to the README](../../README.md)

## Principle

- Messages are described in JSON files placed in the `msgLibrary/msgManual/` folder.
- **One file per function**, named `Msg_<function>.json`: `Msg_Motor.json`, `Msg_Sensors.json`…
- At start, every `Msg_*.json` file is loaded and merged (the old `Message_` prefix is still accepted). Each file becomes a group in the list.
- After a change, click **Reload** in the interface.
- An invalid file is reported in the monitor without preventing the others from loading.

> The device's **protocol commands** (TX / RX part, units, factors) and **error codes** are also described in these files, under the `"commands"` and `"errors"` keys, one or more files per device (`Msg_Regulateur_Exemple.json`): see [PROTOCOL.md](PROTOCOL.md).

## Example

`msgLibrary/msgManual/Msg_Motor.json`:

```json
{
  "group": "Motor",
  "messages": [
    {
      "name": "Set speed",
      "description": "Speed setpoint in rpm",
      "frame": ["AA 55", "20", "{motor}", "{speed}", "{direction}", "{cs}"],
      "params": {
        "motor":     { "type": "u8", "default": 1, "min": 1, "max": 4 },
        "speed":     { "type": "u16be", "default": 1500, "min": 0, "max": 3000, "unit": "rpm" },
        "direction": { "type": "enum", "choices": { "forward": 0, "reverse": 1 } }
      },
      "checksum": { "algo": "xor8", "start": 2 }
    },
    {
      "name": "Stop",
      "frame": ["AA 55 21 00", "{cs}"],
      "checksum": { "algo": "xor8", "start": 2 }
    }
  ]
}
```

With the default values, "Set speed" gives `AA 55 20 01 05 DC 00 F8`.

## File structure

| Key | Required | Role |
|---|---|---|
| `group` | no | Displayed group name. Default: the file name after `Msg_`. Useful for accents (`Msg_Systeme.json` → `"Système"`) |
| `messages` | yes | List of messages |
| `protocol` | no | Protocol the file was written for (`"Modbus RTU"`, or a list of names). Information shown in the Manual tab; for commands (`"commands"`), a file written for another protocol is skipped. See [CONF_PROTOCOL.md §12](CONF_PROTOCOL.md#12-link-with-the-command-files) |

## Message structure

| Key | Required | Role |
|---|---|---|
| `name` | yes | Name shown in the list |
| `frame` | yes (except protocol message) | Frame composition (see below); or `request`: [protocol message](#protocol-message-request) |
| `description` | no | Help text shown above the parameters |
| `params` | no | Definition of the parameters used in `frame` |
| `checksum` | no | Checksum computation, if `{cs}` appears in `frame` |
| `group` | no | Forces the group for this message only |

## Protocol message (`request`)

Instead of describing the bytes with `frame`, a message can give only what the Protocol tab asks for: the frame is then **built by the current protocol** (length, header and DATA CRC included).

```json
{
  "name": "Write running state",
  "description": "Command 0x8010, DATA = 01",
  "request": {
    "request_id": 5,
    "command_id": "0x8010",
    "data": "01"
  }
}
```

| `request` key | Required | Role |
|---|---|---|
| `command_id` | yes | COMMAND ID (`"0x80010001"` or a number) |
| `request_id` | no | REQUEST ID (missing: protocol without REQUEST ID) |
| `data` | no | DATA in hex (`""` = no data) |
| `header` | no | Other header fields, by name or role: `{"CI": "0x52"}` |
| `variant` | no | Frame format, for a protocol with variants (`"Longue"`) |

- In the Manual tab, **REQUEST ID**, **COMMAND ID** and **DATA** are shown as **editable** parameters; the frame (in the protocol's colours) follows every change, CRC included.
- The **Save…** button of the Protocol tab saves the displayed request in this format: it asks for the message name (the suggested file, `Msg_<name>.json`, is shown live: spaces replaced by `_`), then opens the file browser on `msgLibrary/msgManual/` with this file pre-filled, which can still be changed (`Msg_` prefix added if needed; a file created this way has the group "Sauvegardés"). Choosing an existing file adds the message to it. If the name already exists in the file: **Yes** replaces it, **No** keeps both (the new one becomes "name (2)"), **Cancel** writes nothing; an identical message is not written again. A file chosen outside `msgLibrary/msgManual/` is loaded anyway and remembered with the files added by **Load…** (`settings.json`, `message_files`): the list of the Manual tab stays complete after the save and at the next start; **Remove** takes it out. This file is rewritten by SerialHex: rename it to keep your own comments.
- **Duplicates when loading**: a message identical to one already loaded (the group does not count: copy of a file under another name) is skipped; two messages with the same name in the same group but different contents are kept, with the name of the source file in brackets in the list.
- Under DATA, the **Value** section converts DATA both ways according to the command of the current protocol (fields in green), or reads it as an integer if the command is unknown (in blue); **Hex** checkbox for integers. See [GUI.md](GUI.md#messages-left).
- The frame depends on the chosen protocol: "Written for" is shown in orange if the message was written for another protocol.

## Frame (`frame`)

List of pieces concatenated in order:

| Piece | Meaning |
|---|---|
| `"AA 55"` | fixed bytes in hex (spaces optional) |
| `"{name}"` | value of the `name` parameter |
| `"{cs}"` | position of the checksum |

## Parameters (`params`)

### Types

| Type | Size | Input |
|---|---|---|
| `u8` / `i8` | 1 byte | `12`, `0x0C`, `0b1100` |
| `u16be` / `u16le` / `i16be` / `i16le` | 2 bytes | `512`, `0x0200` |
| `u32be` / `u32le` / `i32be` / `i32le` | 4 bytes | `100000` |
| `bool` | 1 byte (0/1) | checkbox |
| `enum` | depends on `size` (default `u8`) | drop-down list |
| `hex` / `raw` | variable | `DE AD BE EF` (raw bytes, no conversion) |
| `ascii` | variable, or fixed with `length` | `HELLO` |

`be` = big endian (most significant byte first), `le` = little endian.

### Options

| Option | Types | Role |
|---|---|---|
| `label` | all | Displayed label (default: the parameter name) |
| `default` | all | Initial value |
| `min` / `max` | integers | Bounds checked before sending |
| `unit` | all | Unit shown next to the field |
| `choices` | `enum` | Dictionary `{"label": value}` |
| `size` | `enum` | Type of the byte sent (`u8`, `u16be`…) |
| `length` | `ascii` | Fixed length, padded with `00` |

## Checksums (`checksum`)

```json
"checksum": { "algo": "xor8", "start": 2 }
```

| `algo` | Description | Size |
|---|---|---|
| `xor8` | XOR of all bytes | 1 byte |
| `sum8` | 8-bit sum | 1 byte |
| `sum8_2c` | two's complement of the sum | 1 byte |
| `crc8` | CRC-8 (polynomial 0x07) | 1 byte |
| `crc16_modbus` | CRC-16 Modbus | 2 bytes, little endian |

`start`: index of the first byte included in the computation. Example: `2` to exclude the `AA 55` header. The computation stops just before `{cs}`.

## Merging the files

To gather every file into a single one, for example to share it:

```bash
python serialhex.py --merge
```

Creates `messages_merged.json` at the root of the project, loadable with the **Load…** button. Each message keeps its group.
