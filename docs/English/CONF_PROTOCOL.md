# Protocol file: every option

[← Back to the README](../../README.md) · [Protocol and Protocol tab](PROTOCOL.md)

SerialHex is **standard** software: the frame structure of a device is described in a **protocol file** (`protocols/` folder), without touching the code. This document lists **every** possible key, with its role and examples.

- The file is JSON (UTF-8). Numbers are written in decimal (`83`) or as hex / binary text (`"0x7E"`, `"0b0101"`).
- **Comments** are accepted, as in VS Code: `// to the end of the line` and `/* over several lines */` (a `//` inside a string, such as `"http://…"`, is not a comment). VS Code opens `protocols/*.json` as "JSON with Comments".
- **A key set to `null` is ignored**: every key can be kept in a field, filled in when used, `null` otherwise: `{"name": "SYNC", "size": 1, "role": "value", "value": "0x7E", "LENb": null, "at": null, "if": null}`.
- An invalid file is reported in the monitor with the exact reason, and SerialHex uses the built-in generic protocol instead.
- The same file is read by the Python tool and by the TypeScript package of the React GUI (`parseProtocol`).
- Summary of every key and possible value, in plain text: `protocols/README_CONF.txt` (in French: `protocols/LISEZMOI_CONF.txt`).

**Files shipped with the Techmelec version** (all commented in French and English):

| File | Protocol | Features shown |
|---|---|---|
| `modbus_rtu.json` | Modbus RTU | CRC least significant byte first, normal / exception response (variants + bits) |
| `modbus_ascii.json` | Modbus ASCII | `ascii_hex` encoding (`:` … CR LF), LRC |
| `modbus_tcp.json` | Modbus TCP | MBAP header, length, TCP link |
| `mbus.json` | M-Bus | 3 formats (E5 / short / long), repeated length (`copy`), 8-bit sum, little endian |
| `profibus_fdl.json` | PROFIBUS FDL | SD1 / SD2 / SD3 / SD4 / E5, addresses with extension bit (`LENb`) |
| `exemple_generique.json` | template | SYNC AA 55, 16-bit sequence number, CRC16 CCITT |

Standard Modbus functions for any device: `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json`. Example commands for **fictitious** devices: `msgLibrary/msgList/modbus/`, `msgLibrary/msgList/mbus/`, `msgLibrary/msgList/profibus/`.

## Contents

1. [File keys](#1-file-keys)
2. [Field keys](#2-field-keys)
3. [Roles](#3-roles)
4. [CRCs and sums](#4-crcs-and-sums)
5. [CRC range: `over`](#5-crc-range-over)
6. [Data size](#6-data-size)
7. [Conditions: `if`](#7-conditions-if)
8. [Field placement: `at` and `after`](#8-field-placement-at-and-after)
   - [8 bis. Bit fields: `LENb`, `atb`, `bit_order`](#8-bis-bit-fields-lenb-atb-bit_order)
   - [8 ter. Several frame formats: `variants`](#8-ter-several-frame-formats-variants)
   - [8 quater. Line encoding: `encoding`](#8-quater-line-encoding-encoding)
9. [Colours](#9-colours)
   - [9 bis. Readable texts: descriptions, values, categories](#9-bis-readable-texts-descriptions-values-categories)
10. [Complete examples](#10-complete-examples)
11. [Error messages at load time](#11-error-messages-at-load-time)
12. [Link with the command files](#12-link-with-the-command-files)

## 1. File keys

| Key | Required | Values | Role |
|---|---|---|---|
| `name` | no (file name by default) | text | Name shown in the list of the Protocol tab; `Msg_*.json` files refer to it (`protocol` key) |
| `description` / `description_en` | no | text | Shown next to the list (in English if the interface is in English) |
| `byte_order` | no (`little`) | `little`, `big` | Byte order of every field and CRC longer than one byte. `little`: least significant first (`0x1234` → `34 12`); `big`: most significant first (`0x1234` → `12 34`, Modbus registers, network order) |
| `encoding` | no (`binary`) | `"binary"`, `{"type": "ascii_hex", …}` | Encoding of the frame on the line (§8 quater) |
| `bit_order` | no (`msb`) | `msb`, `lsb` | Bit numbering for bit fields (§8 bis): `msb` = bit 0 = most significant bit of byte 0 |
| `crc` | no | object `{name: definition}` | CRCs used by the fields, each one named (see §4) |
| `tx` | **yes** | list of fields, or `{"variants": […]}` | **Request** frame (sent to the device), fields in byte order; several formats possible (§8 ter) |
| `rx` | **yes** | list of fields, or `{"variants": […]}` | **Response** frame (received from the device) |
| `commands` | no | path | Folder of the `Msg_*.json` commands, **relative to the protocol file** (`"../messages"`). Missing: no command library |
| `errors` | no | object `{code: text}` or `{code: {"fr": …, "en": …}}` | Texts of the error codes (role `error`). Take precedence over those of the `Msg_*.json` |
| `categories` | no | object `{code: text}` or `{code: {"fr": …, "en": …}}` | Command categories (`group` key of the `Msg_*.json`, e.g. `LAS`, `COM`): text shown with the command description (§9 bis) |
| `_comment` | no | text | Free comment (ignored) |

## 2. Field keys

| Key | For which roles | Values | Role |
|---|---|---|---|
| `name` | all, **required** | text, unique in `tx` (or `rx`) | Name shown in the tables; used as a reference in `over`, `of` and `if` |
| `role` | all | see §3 (upper case accepted: `"NA"`) | What the field represents. Default `value` if `value` is given, otherwise `field` |
| `size` or `LENO` | all (optional for `data` and `crc`) | `value`, `request_id`, `command_id`, `length`, `error`, `field`: **0 to 4**; `na`: 0 to 255; `data`: 0 to 65535 | Size in **bytes**. **`0` = field absent** (it can stay in the file as a reminder). CRC: size of the algorithm by default |
| `LENb` | all except `data` and `crc` | 0 to 32 bits (`na`: 0 to 2040) | Size in **bits**: `"LENO": 1` = `"LENb": 8` (§8 bis). Only one size per field |
| `value` | `value` | integer that fits in `size` | Expected value (checked when decoding, written when building) |
| `default` | `field` | integer | Value written when building if nothing is given (`0` by default) |
| `fill` | `na` | 0 to 255 | Byte written in the unread bytes when building (`0` by default) |
| `of` | `length` | name, or list of names | Field(s) whose length is counted |
| `algo` | `crc` | name from the `crc` section, or ready-made name (§4) | CRC algorithm |
| `over` | `crc` | `[start, end]` (§5) | Bytes covered by the CRC. Default: from the start of the frame up to the CRC |
| `if` | all | name of a field | The field only exists if the named field is present and not empty / not zero (§7) |
| `order` | all numeric fields and CRCs | `little`, `big` | Byte order specific to this field (overrides `byte_order`) |
| `color` | all | `hdr`, `cmd`, `crc`, `na`, or `"#RRGGBB"` | Display colour (§9) |
| `at` or `atO` | all | byte number, `"start"`, `"end"` | Placement of the field (§8) |
| `atb` | all | bit number | Bit-accurate placement: `"atO": 2` = `"atb": 16` (§8 bis) |
| `after` | all | name of a field | Placed right after this field (§8) |
| `same_as` | `copy` | name of a previous field | Copied field (repeated M-Bus / PROFIBUS length) |
| `description` / `description_en` | all | text | Free text, shown in the Description column of the tables (§9 bis) |
| `values` | all numeric fields | `{value: text}` or `{value: {"fr": …, "en": …}}` | Meaning of each value, shown next to the decoded value: `3 (0x03) Read Holding Registers` (§9 bis) |
| `category` | all | text | Free tag (sorting, filters of external tools) |

## 3. Roles

| Role | At most one per direction | Building (sending) | Decoding (receiving) |
|---|---|---|---|
| `value` | no | writes `value` | checks the value; otherwise error `SYNC différent de 0xA55A` and bytes in red. The fixed bytes at the **start** are also used to recognise the protocol's frames in the monitor |
| `request_id` | yes | given value (REQUEST ID field of the tab, shown in hex: `0x05`); the "REQ+" checkbox (auto req_id) goes back to 0 after the maximum (0xFF on 1 byte, 0xFFFF on 2) | links the response to its request: "Auto" response type, reply timeout, summaries `response #0x05` |
| `command_id` | yes | given value (COMMAND ID of the chosen command) | chooses the library command used to decode DATA; if the **response** contains one, it is used directly |
| `length` | yes | computed: size of the fields in `of` | gives the size of DATA |
| `error` | yes | given value (0 by default) | green background at 0, red otherwise; text from `errors`; a response in error is not decoded with the `rx` part of the command |
| `crc` | no | computed last, over the frame already written | checked; red and `attendu XX XX` (expected) if wrong |
| `data` | yes | the bytes of the command's `tx` fields (Protocol tab) | split according to the command's `rx` (or `tx`) fields |
| `field` | no | `default`, or value given by its name | read and shown, without check |
| `na` | no | `size` bytes equal to `fill` | **not read**: neither value nor check, shown grey and struck through, note "non lu" (not read). The bytes stay covered by the CRCs that include them. Several `na` fields possible |
| `copy` | no | copies the value already written of the `same_as` field | checks equality; otherwise error `L (répété) différent de L` |

**Example: reserved bytes to ignore**

```json
{"name": "RESERVED 1", "size": 2, "role": "na"},
{"name": "RESERVED 2", "size": 1, "role": "NA", "fill": "0xFF"}
```

## 4. CRCs and sums

`crc` section: each CRC gets a name, used by the fields (`"algo": "modbus"`). Three ways to write it:

```json
"crc": {
  "modbus": "crc16_modbus",
  "ccitt":  { "preset": "crc16_ccitt_false" },
  "custom": { "width": 16, "poly": "0x1021", "init": "0xFFFF", "refin": false, "refout": false, "xorout": "0x0000" }
}
```

A ready-made name can also be put directly in `algo` (`"algo": "crc32"`), without a `crc` section.

### Ready-made names

| Name | width | poly | init | refin | refout | xorout | Value for `123456789` | Common use |
|---|---|---|---|---|---|---|---|---|
| `crc16_modbus` | 16 | 0x8005 | 0xFFFF | yes | yes | 0 | 0x4B37 | Modbus RTU |
| `crc16_ccitt_false` | 16 | 0x1021 | 0xFFFF | no | no | 0 | 0x29B1 | many serial protocols |
| `crc16_xmodem` | 16 | 0x1021 | 0x0000 | no | no | 0 | 0x31C3 | XMODEM |
| `crc16_kermit` | 16 | 0x1021 | 0x0000 | yes | yes | 0 | 0x2189 | Kermit, CCITT "true" |
| `crc8` | 8 | 0x07 | 0x00 | no | no | 0 | 0xF4 | SMBus |
| `crc8_maxim` | 8 | 0x31 | 0x00 | yes | yes | 0 | 0xA1 | 1-Wire sensors (DS18B20) |
| `crc32` | 32 | 0x04C11DB7 | 0xFFFFFFFF | yes | yes | 0xFFFFFFFF | 0xCBF43926 | zip, Ethernet |
| `crc32_mpeg2` | 32 | 0x04C11DB7 | 0xFFFFFFFF | no | no | 0 | 0x0376E6E7 | MPEG-2, STM32 (CRC unit) |
| `sum8` | 8 | — | — | — | — | — | 0xDD | sum of the bytes, modulo 256 |
| `sum8_2c` | 8 | — | — | — | — | — | 0x23 | two's complement: frame + sum = 0 |
| `xor8` | 8 | — | — | — | — | — | 0x31 | XOR of all bytes (NMEA…) |
| `sum16` | 16 | — | — | — | — | — | 0x01DD | sum of the bytes, modulo 65536 |

The "value for `123456789`" is the check value of CRC catalogues (reveng): it lets you verify a configuration with any online calculator.

### CRC parameters

A CRC is a `width`-bit register into which the bytes are fed one by one; at each bit, if the bit shifted out is 1, the register is combined with the polynomial (XOR).

| Parameter | Meaning |
|---|---|
| `width` | CRC size: 8, 16 or 32 bits (1, 2 or 4 bytes in the frame) |
| `poly` | Polynomial, in **normal** form (implicit most significant bit). Modbus: `0x8005` |
| `init` | Register value before the first byte. Modbus: `0xFFFF` |
| `refin` | **true**: each byte is read starting with its **least** significant bit ("reflected"). **false**: starting with the most significant bit. Protocols inherited from UARTs (Modbus, Kermit, zip) are reflected |
| `refout` | **true**: the final result is reflected (its bits are reversed end to end: bit 0 ↔ bit 15). Almost always equal to `refin` |
| `xorout` | Value combined (XOR) with the final result. `0` = nothing; `0xFFFFFFFF` for crc32 (inverted result) |

**Why is Modbus often given with the polynomial `0xA001`?** `0xA001` is `0x8005` reflected. Datasheets often describe the algorithm "backwards" (register shifted to the right, directly processing the least significant bits): this is exactly `poly 0x8005` with `refin` and `refout` true. In SerialHex, write the normal form `0x8005`, or simply `"crc16_modbus"`.

**Finding the parameters of an unknown CRC**: take a frame whose CRC is known, then try the ready-made names (Free hex field + "Auto CRC", or an online calculator). If none fits, the byte order of the CRC (`order`) or the covered range (`over`) is often the cause.

## 5. CRC range: `over`

`"over": [start, end]`, bounds **included**.

| Bound | Value | Meaning |
|---|---|---|
| start | integer | byte number (0 = first byte of the frame) |
| start | field name | first byte of this field |
| end | integer | byte number |
| end | field name | last byte of this field |
| end | `"end"` | last byte just before the CRC |

| Example | Bytes covered |
|---|---|
| (missing) | the whole frame before the CRC, like `[0, "end"]` |
| `["SYNC", "LEN"]` | the header of the built-in generic protocol |
| `["DATA", "DATA"]` | the data only; empty if there is no data |
| `[1, "end"]` | everything except the first byte (sync byte excluded) |
| `[0, 10]` | bytes 0 to 10, for a fixed frame |

A named field that is absent (empty DATA, `if` field not filled) gives an empty range.

## 6. Data size

| Case | How to write it | Example |
|---|---|---|
| Size given by a length field | a `length` field with `"of": "DATA"`, placed before DATA | generic protocol: LEN on 1 byte |
| Length that also counts the CRC | `"of": ["DATA", "CRC"]` | `01 03 05 06 0F`: length 3 = 2 data bytes + 1 CRC byte |
| Fixed size | `"size": 10` on DATA | 12-byte fixed frame |
| The rest of the frame | DATA without `size` and without a length field; the following fields must have a fixed size | `[SYNC][DATA…][CRC]` |
| No data | `"size": 0` on DATA, or no `data` field | command-only frame |

## 7. Conditions: `if`

`"if": "NAME"`: the field only exists if the field `NAME` is present and:
- for DATA: not empty;
- for a numeric field (length, error code, free field…): not 0;
- for a fixed byte, a CRC or unread bytes: always true.

Examples: `"DATA CRC" ... "if": "DATA"` (data CRC only if there is data); `"PAD" ... "role": "na", "if": "DATA"` (padding bytes after data).

## 8. Field placement: `at` and `after`

By default, fields follow each other **in list order**. Each field can also say where it goes; the order can thus be changed without rewriting the list, or the frame can be described like a specification table ("byte 0: SYNC, bytes 2 to 5: COMMAND ID…").

| Key | Value | Effect |
|---|---|---|
| `"at": 6` | byte number | the field **starts at byte 6**. Bytes left free before it automatically become unread bytes (`(octets 2-3)`, role `na`) |
| `"at": "start"` | | at the **head** of the frame |
| `"at": "end"` | | at the **end** of the frame (final CRC…); several `end` fields stay in list order |
| `"after": "NAME"` | name of a field | **right after** the field NAME; a field placed after another follows it if that one is moved (cascading) |

Rules:
1. base order: the `"at": "start"` fields, then the fields without placement (each followed by its `after` fields);
2. fields at a **fixed byte** win: they take their place, and the others flow around them (before them if they fit entirely, otherwise after);
3. the `"at": "end"` fields close the frame.

A fixed byte must come before any variable-size part (DATA, conditional `if` field).

**Changing the order without rewriting the list**

```json
"tx": [
  {"name": "CRC", "role": "crc", "algo": "sum16", "at": "end"},
  {"name": "DATA", "role": "data", "after": "LEN"},
  {"name": "CMD", "size": 2, "role": "command_id", "at": 4},
  {"name": "RID", "size": 1, "role": "request_id", "after": "SOF"},
  {"name": "LEN", "size": 1, "role": "length", "of": "DATA", "after": "CMD"},
  {"name": "SOF", "size": 1, "value": "0x7E", "at": "start"}
]
```

Resulting order: `SOF` (byte 0) · `RID` (1) · `(octets 2-3)` unread · `CMD` (4-5) · `LEN` (6) · `DATA` · `CRC`.

**Byte map, as in a specification**

```json
"tx": [
  {"name": "SYNC",        "size": 1, "value": "0x7E", "at": 0},
  {"name": "COMMAND ID",  "size": 4, "role": "command_id", "at": 2},
  {"name": "HEADER CRC",  "size": 2, "role": "crc", "algo": "crc16_modbus", "at": 6, "over": [0, 5]}
]
```

Byte 1, not described, becomes `(octet 1)`, unread.

Load messages are in French (the engine's messages are translated in the interface when it is in English):

| Message | Cause |
|---|---|
| `l'octet 1 est déjà occupé (les champs précédents vont jusqu'à l'octet 1)` | two fixed-byte fields overlapping |
| `impossible de le placer à l'octet 3, le champ 'D' qui le précède n'a pas une taille fixe` | fixed byte after a variable-size part |
| `placement circulaire (after) : A, B` | A after B and B after A |
| `after désigne un champ inconnu 'Z'` | misspelt name |
| `"at" et "after" ne peuvent pas être utilisés ensemble` | only one placement per field |
| `le bit 2 est déjà occupé (les champs précédents vont jusqu'au bit 3)` | two bit fields overlapping |
| `une seule taille (size, LENb)` / `une seule position (at, atb)` | two sizes or two positions for the same field |

## 8 bis. Bit fields: `LENb`, `atb`, `bit_order`

A field can have any number of **bits** and start on **any bit**: flags, 3-bit version number, 7-bit function code…

| Key | In bytes | In bits | Equivalence |
|---|---|---|---|
| Size | `"size": 1` or `"LENO": 1` | `"LENb": 8` | `LENO` × 8 = `LENb` |
| Position | `"at": 2` or `"atO": 2` | `"atb": 16` | `atO` × 8 = `atb` |

**Bit numbering** (`bit_order` of the file):

| `bit_order` | Bit 0 | Reading a multi-bit field | Use |
|---|---|---|---|
| `msb` (default) | **most** significant bit of byte 0 | the first bit read is the most significant bit of the value | specification diagrams ("bits 0-2: version"), network headers |
| `lsb` | **least** significant bit of byte 0 | the first bit read is the least significant bit | microcontroller registers, "Intel" frames |

Rules:
- a field that starts and ends on whole bytes is read byte by byte, with `byte_order` / `order`; a bit field is read bit by bit, with `bit_order`;
- DATA and CRCs are whole bytes and start on a byte; a conditional field (`if`) is whole bytes; the frame ends on a whole byte (otherwise: `la trame ne finit pas sur un octet entier (il manque 4 bit(s))`);
- a length (`length`) counts bytes: the counted fields must **together** make whole bytes (one bit + 7 bits = 1 byte, like the Modbus TCP function byte); the length field itself can be in bits;
- gaps left by `atb` become unread bits (`(bits 8-11)`); an `na` bit field is written as 0 (`fill` 0) or 1 (other `fill`);
- position shown as "byte.bit" in the tables (`1.0`, `1.1-1.7`); value in binary (`5 (0b101)`);
- colours: a byte shared between several fields takes the colour of the last one.

**Example: Modbus exception.** In a response, the most significant bit of the function byte signals an exception (`0x83` = exception on function 3). By splitting it (1 bit + 7 bits), the function stays the same as in the request; with two variants (§8 ter), the following byte becomes the error code:

```json
"rx": {"variants": [
  {"name": "Normale", "fields": [
    {"name": "ADDRESS",   "size": 1, "role": "request_id", "color": "hdr"},
    {"name": "EXCEPTION", "LENb": 1, "role": "value", "value": 0},
    {"name": "FUNCTION",  "LENb": 7, "role": "command_id", "color": "cmd"},
    {"name": "DATA",      "role": "data"},
    {"name": "CRC", "size": 2, "role": "crc", "algo": "crc16_modbus", "order": "little", "color": "crc"}]},
  {"name": "Exception", "fields": [
    {"name": "ADDRESS",   "size": 1, "role": "request_id", "color": "hdr"},
    {"name": "EXCEPTION", "LENb": 1, "role": "value", "value": 1},
    {"name": "FUNCTION",  "LENb": 7, "role": "command_id", "color": "cmd"},
    {"name": "EXCEPTION CODE", "size": 1, "role": "error"},
    {"name": "CRC", "size": 2, "role": "crc", "algo": "crc16_modbus", "order": "little", "color": "crc"}]}
]}
```

`01 83 02 C0 F1` → Exception variant: ADDRESS 1, FUNCTION 3, EXCEPTION CODE 2 (red background, `error 2 (Illegal data address)` from `errors`).

**Example: split command byte** (`bit_order` `msb`):

```json
"tx": [
  {"name": "VERSION", "LENb": 3, "value": 2, "color": "hdr"},
  {"name": "TYPE",    "LENb": 5, "role": "command_id", "color": "cmd"},
  {"name": "URGENT",  "LENb": 1, "role": "field", "atb": 12},
  {"name": "SEQ",     "LENO": 1, "role": "request_id", "atO": 2}
]
```

`TYPE` 0x15: byte 0 = `010 10101` = `0x55`; `URGENT` at bit 12 (bit 4 of byte 1): byte 1 = `0x08`; bits 8-11 and 13-15 are unread bits.

## 8 ter. Several frame formats: `variants`

Some protocols have several frame formats, recognised by their fixed bytes: M-Bus (`E5`, short frame `10…16`, long frame `68 L L 68…16`), PROFIBUS (SD1 to SD4), Modbus normal / exception response. `tx` and `rx` can then contain a list of **variants**:

```json
"rx": {
  "variants": [
    {"name": "Accusé", "description": "Accusé E5", "description_en": "E5 acknowledge",
     "fields": [ {"name": "ACK", "size": 1, "role": "value", "value": "0xE5"} ]},
    {"name": "Longue",
     "fields": [ {"name": "START", "size": 1, "value": "0x68"}, … ]}
  ]
}
```

| Rule | Detail |
|---|---|
| Name | `name` required and unique; shown in the **Format** list of the Protocol tab (request) |
| Fields | each variant is a complete field list, checked like a plain `tx` / `rx`; names can repeat from one variant to another |
| Decoding | the variant is chosen from the **fixed bytes** (`value`); if several fit, the first one that decodes without error |
| Building | the variant chosen in the **Format** list, or the command's (`"variant"` in the `Msg_*.json`); the first one by default |
| Summaries | REQUEST ID, COMMAND ID… are looked up in the first variant that has one |

A response without REQUEST ID (`E5` acknowledge) stops the timeout monitoring of the oldest pending request.

## 8 quater. Line encoding: `encoding`

By default the frame is sent as is (`"encoding": "binary"`). Modbus ASCII writes each byte as two hex characters, between a start and an end:

```json
"encoding": {"type": "ascii_hex", "start": ":", "end": "\r\n", "lowercase": false}
```

| Key | Default | Role |
|---|---|---|
| `type` | `binary` | `binary` or `ascii_hex` |
| `start` | `":"` | start character(s) |
| `end` | `"\r\n"` | end of frame; also used to **cut received frames** as soon as it arrives, without waiting for the silence |
| `lowercase` | `false` | hex in lower case |

Fields, lengths and CRCs (LRC `sum8_2c`) apply to the **binary** frame; the preview and the monitor colour the characters sent. Messages: `début de trame ':' absent` (start missing), `fin de trame '\r\n' absente` (end missing), `caractères hexa ASCII invalides` (invalid ASCII hex characters).

`01 03 00 00 00 0A` (LRC `F2`) is sent as `:01030000000AF2` CR LF.

## 9. Colours

| `color` | Display | Recommended use |
|---|---|---|
| `hdr` | light grey | fixed bytes and numbers of the header (sync, address, REQUEST ID) |
| `cmd` | bold | command identifier |
| `crc` | pastel green (red if wrong) | CRCs and sums |
| `na` | very light grey, struck through | unread bytes (default for the `na` role) |
| `"#FF8800"` | exactly this colour | a field you want to spot (one colour per field if needed) |
| (nothing) | colour of the line (TX blue, RX purple in the monitor) | data, lengths |

The actual colours of `hdr`, `cmd`, `crc`, `na`, the errors and the TX / RX lines are set in the interface: **Colours…** button (see [GUI.md](GUI.md#colours)). A `"#RRGGBB"` colour written in the file does not change with this setting.

The error code (role `error`) always has a green background at 0, red otherwise. A wrong fixed byte or CRC is red, whatever its colour. Colours only apply to a complete frame.

## 9 bis. Readable texts: descriptions, values, categories

So that a file can be read without the specification at hand:

```json
{"name": "FUNCTION", "size": 1, "role": "command_id", "color": "cmd",
 "description": "Code fonction Modbus", "description_en": "Modbus function code",
 "values": {
   "0x03": {"fr": "Lecture de registres", "en": "Read Holding Registers"},
   "0x06": "Write Single Register"
 }}
```

| Key | Where | Display |
|---|---|---|
| `description` / `description_en` | file, variant, field | **Description** column of the tables, next to the protocol list; the English version if the interface is in English (falls back to French) |
| `values` | numeric field | next to the decoded value: `3 (0x03) Read Holding Registers`; keys in decimal or hex |
| `errors` | file | text of the error code; plain text or `{"fr", "en"}` |
| `categories` | file | text of a command's category (`"group": "READ"` → "Read — …" before the description) |
| `category` | field | free tag, no effect on the bytes |

These keys change nothing in the bytes built or decoded.

## 10. Complete examples

### Public protocols supplied

The complete files, commented line by line, are in `protocols/`. Reference frames (checked by the tests):

| File | Frame | Meaning |
|---|---|---|
| `modbus_rtu.json` | `01 03 00 00 00 02 C4 0B` | slave 1, read 2 registers from 0 |
| | `01 03 04 00 E6 00 01 DA 04` | response: 2 registers, 0x00E6 and 0x0001 |
| | `01 83 02 C0 F1` | exception 2 (illegal address), Exception variant |
| `modbus_ascii.json` | `:01030000000AF2` CR LF | read 10 registers, LRC `F2` |
| `modbus_tcp.json` | `00 01 00 00 00 06 01 03 00 00 00 0A` | transaction 1, length 6, unit 1 |
| `mbus.json` | `10 5B 05 60 16` | REQ_UD2 to address 5 (short frame) |
| | `68 03 03 68 53 05 50 A8 16` | SND_UD, CI 0x50: reset (long frame, repeated L) |
| | `E5` | acknowledge |
| `profibus_fdl.json` | `10 05 02 49 50 16` | SD1: FDL status request from master 2 to slave 5 |
| | `68 05 05 68 85 82 6D 3C 3E EE 16` | SD2: DP diagnostics, addresses with extension bit, SAP 60 → 62 |

### 2-byte SYNC, 16-bit sequence number, reserved bytes, CRC32

```json
{
  "name": "CRC32 example",
  "byte_order": "big",
  "crc": { "c": "crc32" },
  "tx": [
    {"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
    {"name": "SEQ", "size": 2, "role": "request_id", "color": "hdr"},
    {"name": "RESERVED", "size": 2, "role": "na"},
    {"name": "CMD", "size": 1, "role": "command_id", "color": "cmd"},
    {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
    {"name": "DATA", "role": "data"},
    {"name": "CRC", "role": "crc", "algo": "c", "over": [2, "end"], "color": "crc"}
  ],
  "rx": [
    {"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
    {"name": "SEQ", "size": 2, "role": "request_id", "color": "hdr"},
    {"name": "RESERVED", "size": 2, "role": "na"},
    {"name": "STATUS", "size": 1, "role": "error"},
    {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
    {"name": "DATA", "role": "data"},
    {"name": "CRC", "role": "crc", "algo": "c", "over": [2, "end"], "color": "crc"}
  ],
  "errors": { "0": "OK", "1": "Unknown command", "2": "Invalid parameter" }
}
```

The CRC excludes the SYNC (`over` starts at byte 2).

### 12-byte fixed frame, CRC8 over bytes 0 to 10

```json
{
  "name": "Fixed frame",
  "tx": [
    {"name": "STX", "size": 1, "value": 2, "color": "hdr"},
    {"name": "DATA", "role": "data", "size": 10},
    {"name": "CRC", "role": "crc", "algo": "crc8", "over": [0, 10], "color": "crc"}
  ],
  "rx": [
    {"name": "STX", "size": 1, "value": 2, "color": "hdr"},
    {"name": "DATA", "role": "data", "size": 10},
    {"name": "CRC", "role": "crc", "algo": "crc8", "over": [0, 10], "color": "crc"}
  ]
}
```

### Without request number or command identifier

```json
{"name": "REQUEST ID", "size": 0, "role": "request_id"}
```

A field of size 0 is absent from the frame: the corresponding field is greyed out in the Protocol tab, the response is attached to the last request sent and the reply timeout is not monitored.

## 11. Error messages at load time

The messages are written in French in the files' error report (translated in the interface when it is in English):

| Message (extract) | Cause |
|---|---|
| `"tx" : liste de champs attendue` | `tx` or `rx` missing or empty |
| `byte_order doit valoir little ou big` | typo |
| `champ 'X' : "size" manquant` | size required for this role |
| `champ 'X' : size doit valoir 0 à 4` | size too large (0 to 255 for `na`) |
| `champ 'X' : rôle 'truc' inconnu (…)` | misspelt role |
| `noms en double : X` | two fields with the same name in `tx` (or `rx`) |
| `un seul champ de rôle 'data'` | two fields with the same unique role |
| `CRC 'x' ni défini dans "crc" ni connu` | unknown `algo` |
| `size 2 incompatible avec crc8 (1 octet(s))` | size ≠ CRC size |
| `over désigne un champ inconnu 'X'` / `of …` / `"if" …` | misspelt field name |
| `la longueur 'L' doit précéder le champ 'DATA'` | length field placed after what it counts |
| `value ne tient pas sur 1 octet(s)` | fixed value too large |
| `fill doit valoir 0 à 255 (un octet)` | invalid fill byte |
| `après une DATA de taille variable, les champs doivent avoir une taille fixe` | "rest of the frame" DATA followed by another variable part |
| `JSON invalide (ligne 12) : …` | missing comma or quote (`//` comments are accepted) |
| `"rx" : chaque variante doit avoir un "name"` / `variantes en double : X` | badly named variants (§8 ter) |
| `"same_as" manquant (champ recopié)` / `le champ recopié 'L' doit le précéder` | incomplete `copy` field or placed before the original |
| `encoding : type inconnu (binary ou ascii_hex)` | misspelt `encoding` |
| `les champs comptés par of doivent faire ensemble des octets entiers (15 bits)` | length over bit fields that do not make whole bytes |

## 12. Link with the command files

Command keys useful with these protocols (details: [PROTOCOL.md](PROTOCOL.md#a-command)):

| Key | Example | Role |
|---|---|---|
| `variant` | `"Courte"` | request frame format (M-Bus, PROFIBUS) |
| `header` | `{"CI": "0x52"}` | values of header fields specific to the command; tells apart commands with the same COMMAND ID |
| `match` | `{"register": "0x0010"}` | values of `tx` fields that tell apart commands with the same COMMAND ID (Modbus: same function, different register) |
| `name_en`, `description_en`, `label_en` | | texts in English |
| `attributes` | `{"access": "R"}` | free fields shown with the description |
| `hidden` | `true` | command hidden in the lists, recognised when decoding ([PROTOCOL.md](PROTOCOL.md#hidden-commands-hidden)) |

Each `Msg_*.json` file states which protocol it was written for:

```json
{
  "protocol": "Modbus RTU",
  "group": "READ",
  "commands": [ … ]
}
```

- `protocol`: name (`name` of the protocol file), or list of names. Compared without regard to case.
- The commands of a file written for **another** protocol are skipped (reported in the monitor: `Msg_X.json skipped: written for protocol …`, or `N command file(s) skipped` when there are several).
- Without a `protocol` key, the file suits every protocol.
- In the Manual tab, the target protocol is shown under the message description (in orange if it differs from the current protocol).
