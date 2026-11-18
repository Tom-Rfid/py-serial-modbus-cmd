===============================================================================================
 SerialHex - PROTOCOL AND COMMAND FILES: ALL KEYS AND POSSIBLE VALUES
 (version française : LISEZMOI_CONF.txt)
===============================================================================================

This folder holds one .json file per protocol. SerialHex reads the frame structure from this
file: a new device is described without touching the code. The device commands (name, data
sent / received, units) live in msgLibrary/msgList/…/Msg_*.json files.

Detailed documentation, with more examples: docs/English/CONF_PROTOCOL.md, docs/English/PROTOCOL.md
(French: docs/Francais/).

Contents
   1. Writing rules
   2. Skeleton of a protocol file
   3. File keys
   4. Field keys
   5. Field roles ("role")
   6. Sizes and positions (bytes / bits)
   7. CRCs and checksums ("crc", "algo", "over")
   8. Several frame formats ("variants")
   9. Line encoding ("encoding")
  10. Colours ("color")
  11. Human-readable texts (description, values, categories, errors)
  12. Command files Msg_*.json
  13. Complete examples
  14. Files provided


-----------------------------------------------------------------------------------------------
 1. WRITING RULES
-----------------------------------------------------------------------------------------------

  - UTF-8 JSON. Comments are accepted:   // up to the end of the line
                                         /* over several lines */
    (a // inside a string, such as "http://...", is not a comment)
  - Numbers in decimal (83) or as hex / binary text ("0x7E", "0b0101").
  - A key set to null is ignored: a field can list every key, fill in the useful ones and set
    the others to null:
      {"name": "SYNC", "size": 1, "role": "value", "value": "0x7E", "LENb": null, "if": null}
  - An invalid file is reported in the monitor with the exact reason (field name, key at
    fault); SerialHex then falls back on its built-in generic protocol.
  - "Reload" button (Manual tab): reads the file again after a change.
  - Field names in the provided files are French (ADRESSE = address, FONCTION = function,
    DONNÉES = data); each field has a "description_en".


-----------------------------------------------------------------------------------------------
 2. SKELETON OF A PROTOCOL FILE
-----------------------------------------------------------------------------------------------

  {
    "name": "My device",                     // name shown in the protocol list
    "description": "…", "description_en": "…",
    "byte_order": "big",                     // byte order of multi-byte fields
    "bit_order": "msb",                      // bit numbering (bit fields)
    "encoding": "binary",                    // line encoding
    "crc": { "modbus": "crc16_modbus" },     // named CRCs, used by "algo"
    "categories": { "LAS": {"fr": "…", "en": "…"} },
    "tx": [ field, field, … ],               // REQUEST frame (sent)
    "rx": [ field, field, … ],               // RESPONSE frame (received)
    "errors": { "0": "OK", "4": "Unknown command" },
    "commands": "../messages"                // Msg_*.json folder, relative to this file
  }

  A field:
    { "name": "COMMAND ID", "size": 4, "role": "command_id", "color": "cmd",
      "description_en": "Command identifier" }


-----------------------------------------------------------------------------------------------
 3. FILE KEYS
-----------------------------------------------------------------------------------------------

  Key              Required   Possible values                         Default
  ---------------  ---------  --------------------------------------  ----------------------
  name             no         text                                    file name
  description      no         text (French)                           ""
  description_en   no         text (English)                          ""
  byte_order       no         "little" | "big"                        "little"
  bit_order        no         "msb" | "lsb"                           "msb"
  encoding         no         "binary" | {"type": "ascii_hex", …}     "binary"
  crc              no         {name: preset or definition}            {}
  categories       no         {code: text or {"fr", "en"}}            {}
  tx               YES        list of fields | {"variants": [...]}
  rx               YES        list of fields | {"variants": [...]}
  errors           no         {code: text or {"fr", "en"}}            {}
  commands         no         relative path ("../messages")           no commands
  _comment         no         free text (ignored)

  byte_order
    "little"  least significant byte first: 0x1234 -> 34 12   (Intel, M-Bus, Modbus CRC)
    "big"     most significant byte first:  0x1234 -> 12 34   (Modbus registers, network order)
    Applies to all numeric fields and CRCs; "order" on a field overrides it.

  bit_order (only for fields that are not whole bytes, see §6)
    "msb"     bit 0 = most significant bit of byte 0; a field is read MSB first
    "lsb"     bit 0 = least significant bit of byte 0; a field is read LSB first


-----------------------------------------------------------------------------------------------
 4. FIELD KEYS
-----------------------------------------------------------------------------------------------

  Key              For roles               Values                           Purpose
  ---------------  ----------------------  -------------------------------  -------------------
  name             all (REQUIRED)          text, unique in tx (or rx)       name, used as reference
  role             all                     see §5                           what the field is
  size / LENO      all                     bytes: 0 to 4 (na 0-255,         size in BYTES
                                           data 0-65535); 0 = absent
  LENb             all but data, crc       bits: 0 to 32                    size in BITS
  at / atO         all                     byte number | "start" | "end"    position in bytes
  atb              all                     bit number                       position in bits
  after            all                     field name                       right after that field
  value            value                   integer                          expected fixed value
  default          field                   integer                          value when sending
  fill             na                      0 to 255                         byte written when sending
  of               length                  name or list of names            counted fields
  algo             crc                     name ("crc" section or §7)       algorithm
  over             crc                     [start, end]                     covered bytes
  order            numeric, crc            "little" | "big"                 field's own byte order
  if               all                     field name                       present if that field is
  same_as          copy                    name of an earlier field         copied field
  color            all                     "hdr" | "cmd" | "crc" | "na" |   colour
                                           "#RRGGBB"
  description      all                     text (French)                    Description column
  description_en   all                     text (English)                   same, in English
  values           numeric                 {value: text or {"fr","en"}}     meaning of each value
  category         all                     text                             free label

  Default role: "value" if the value key is given, otherwise "field".
  One size (size or LENb) and one position (at, atb or after) per field.


-----------------------------------------------------------------------------------------------
 5. FIELD ROLES ("role")
-----------------------------------------------------------------------------------------------

  Role         Only one?  When sending                       When receiving
  -----------  ---------  ---------------------------------  -----------------------------------
  value        no         writes "value"                     checks it; red if different.
                                                             Fixed bytes at the start are used to
                                                             recognise the protocol's frames
  request_id   yes        value entered (REQUEST ID)         matches the reply to its request,
                                                             reply timeout, "response #0x05"
  command_id   yes        the command's COMMAND ID           selects the command to decode DATA
  length       yes        computed: size of the "of" fields  gives the DATA size
  error        yes        value given (0)                    green background at 0, red otherwise;
                                                             text from "errors"
  crc          no         computed last                      checked; red + "expected XX" if wrong
  data         yes        command data                       split according to the command
  field        no         "default" or value given           shown, not checked
  na           no         "fill" (unread bytes)              ignored: grey struck-through, "unread"
  copy         no         copies the "same_as" field         checks equality (repeated length)

  Examples:
    {"name": "SYNC", "size": 1, "role": "value", "value": "0x7E"}
    {"name": "RESERVED", "size": 2, "role": "na", "fill": "0xFF"}
    {"name": "L (repeated)", "size": 1, "role": "copy", "same_as": "L"}


-----------------------------------------------------------------------------------------------
 6. SIZES AND POSITIONS (BYTES / BITS)
-----------------------------------------------------------------------------------------------

  "size": 1  =  "LENO": 1  =  "LENb": 8          "at": 2  =  "atO": 2  =  "atb": 16

  DATA size:
    - a "length" field with "of": "DATA" (placed before DATA)   -> size given by the frame
    - "of": ["DATA", "CRC"]                                     -> the length also counts the CRC
    - "size": 10 on DATA                                        -> fixed size
    - neither size nor length                                   -> rest of the frame (Modbus RTU)

  Placement (by default, fields follow each other in list order):
    "at": 6         starts at byte 6; free bytes before it become unread bytes
    "at": "start"   at the start of the frame    "at": "end"   at the end (final CRC)
    "after": "LEN"  right after field LEN
    "atb": 12       starts at bit 12 (bit 4 of byte 1)

  Bit fields: DATA and CRCs start on a byte; an "if" field is a whole number of bytes; the
  frame ends on a whole byte; fields counted by a length add up to whole bytes.
    Example (Modbus response function byte: 1 exception bit + 7 function bits):
      {"name": "EXCEPTION", "LENb": 1, "role": "value", "value": 0},
      {"name": "FONCTION",  "LENb": 7, "role": "command_id"}

  Condition "if": "NAME": the field exists only if NAME is present and not empty (DATA) or not
  zero (numeric field). E.g. "DATA CRC" with "if": "DATA".


-----------------------------------------------------------------------------------------------
 7. CRCs AND CHECKSUMS ("crc", "algo", "over")
-----------------------------------------------------------------------------------------------

  Presets (usable directly in "algo", or in the "crc" section):

  Name                Width   poly        init        refin/out  xorout      Usage
  ------------------  ------  ----------  ----------  ---------  ----------  ------------------
  crc16_modbus        16      0x8005      0xFFFF      yes        0           Modbus RTU
  crc16_ccitt_false   16      0x1021      0xFFFF      no         0           serial protocols
  crc16_xmodem        16      0x1021      0x0000      no         0           XMODEM
  crc16_kermit        16      0x1021      0x0000      yes        0           Kermit
  crc8                8       0x07        0x00        no         0           SMBus
  crc8_maxim          8       0x31        0x00        yes        0           1-Wire
  crc32               32      0x04C11DB7  0xFFFFFFFF  yes        0xFFFFFFFF  zip, Ethernet
  crc32_mpeg2         32      0x04C11DB7  0xFFFFFFFF  no         0           STM32
  sum8                8       byte sum modulo 256                            M-Bus, PROFIBUS
  sum8_2c             8       two's complement of the sum                    Modbus ASCII LRC
  xor8                8       XOR of all bytes                               NMEA
  sum16               16      byte sum modulo 65536

  "crc" section: three ways to write it
    "crc": {
      "a": "crc16_modbus",                                          // preset
      "b": {"preset": "crc16_ccitt_false"},                          // same
      "c": {"width": 16, "poly": "0x1021", "init": "0xFFFF",          // full definition
            "refin": false, "refout": false, "xorout": "0x0000"}
    }
    width: 8, 16 or 32. refin / refout: true = bytes read least significant bit first
    ("reflected"). The Modbus polynomial often written 0xA001 is 0x8005 reflected.

  "over": [start, end], bounds included
    start: byte number, or field name (its first byte)
    end:   byte number, field name (its last byte), or "end" (just before the CRC)
    absent = [0, "end"]
    E.g.: ["SYNC", "LEN"]             ["DATA", "DATA"]   [1, "end"]   [0, 10]


-----------------------------------------------------------------------------------------------
 8. SEVERAL FRAME FORMATS ("variants")
-----------------------------------------------------------------------------------------------

  For a protocol with several formats, recognised by their fixed bytes (M-Bus: E5 / short
  frame 10 / long frame 68; PROFIBUS: SD1 to SD4; normal / exception response):

    "rx": { "variants": [
      { "name": "Accusé", "description": "…", "description_en": "Acknowledge",
        "fields": [ {"name": "ACK", "size": 1, "role": "value", "value": "0xE5"} ] },
      { "name": "Longue",
        "fields": [ {"name": "START", "size": 1, "role": "value", "value": "0x68"}, … ] }
    ]}

  - name required and unique; each variant has its complete list of fields.
  - Receiving: variant chosen from the fixed bytes.
  - Sending: "Format" list of the Protocol tab, or the command's "variant" key.


-----------------------------------------------------------------------------------------------
 9. LINE ENCODING ("encoding")
-----------------------------------------------------------------------------------------------

  "encoding": "binary"                       bytes sent as they are (default)
  "encoding": {"type": "ascii_hex",          each byte as 2 ASCII hex characters
               "start": ":",                 start of frame
               "end": "\r\n",                end of frame (also splits received frames)
               "lowercase": false}           lower-case hex?

  Fields, lengths and CRCs apply to the binary frame.
  E.g. Modbus ASCII: 01 03 00 00 00 0A + LRC F2  ->  :01030000000AF2<CR><LF>


-----------------------------------------------------------------------------------------------
 10. COLOURS ("color")
-----------------------------------------------------------------------------------------------

  "hdr"       light grey         fixed bytes, addresses, numbers (header)
  "cmd"       bold               command identifier
  "crc"       pastel green       CRCs and checksums (red if wrong)
  "na"        grey struck        unread bytes (default for role na)
  "#FF8800"   that colour        a field to spot
  (absent)    line colour        TX blue, RX purple

  The error role always has a green (0) or red (other value) background. The hdr, cmd, crc,
  na, TX, RX colours are set in the interface ("Colours…" button).


-----------------------------------------------------------------------------------------------
 11. HUMAN-READABLE TEXTS (description, values, categories, errors)
-----------------------------------------------------------------------------------------------

  No effect on the bytes; shown in the tables and the monitor. A text is either a string, or
  {"fr": "…", "en": "…"} to follow the interface language.

    "description": "Code fonction Modbus", "description_en": "Modbus function code"
    "values": { "0x03": {"fr": "Lecture de registres", "en": "Read Holding Registers"},
                "0x06": "Write Single Register" }
        -> shown as "3 (0x03) Read Holding Registers"
    "categories": { "READ": {"fr": "Lecture", "en": "Read"},
                    "WRITE": "Write" }
        -> a command with "group": "READ" shows "Read — …"
    "errors": { "0": "OK", "2": {"fr": "Adresse invalide", "en": "Illegal data address"} }
        -> "error 2 (Illegal data address)" in red in the monitor


-----------------------------------------------------------------------------------------------
 12. COMMAND FILES Msg_*.json
-----------------------------------------------------------------------------------------------

  File:
    "protocol"  : target protocol name, or list; absent = all protocols
    "group"     : default category of the commands (e.g. "LAS", "COM", "READ")
    "hidden"    : true = every command of the file hidden (see "hidden" below)
    "commands"  : list of commands
    "errors"    : {code: text or {"fr", "en"}}
    "messages"  : free frames of the Manual tab (see docs/English/MESSAGES.md)

  Command:
    Key             Required  Purpose
    --------------  --------  ----------------------------------------------------------------
    name            YES       displayed name
    id              YES       COMMAND ID ("0x80000004", "0x03")
    name_en         no        English name
    description     no        text shown under the command; description_en in English
    group           no        category (readable text in the protocol's "categories")
    tx              no        DATA fields of the request ([] = no data)
    rx              no        DATA fields of the response
    presets         no        [{"name": "50 %", "values": {"field": value}}]
    variant         no        request frame format (§8)
    header          no        header field values: {"CI": "0x52"}; tells apart commands with
                              the same COMMAND ID
    match           no        tx field values that tell apart commands with the same
                              COMMAND ID: {"register": "0x0010"} (Modbus). A command
                              without match on the same COMMAND ID is the fallback (generic)
    attributes      no        free fields shown: {"access": "R", "level": "expert"}
    hidden          no        true = hidden command: not in the Protocol tab lists (unless
                              the "Hidden" box is ticked), but still recognised when
                              decoding. Obsolete or internal commands, or commands commented
                              out in the device code. May share its COMMAND ID with a visible
                              command (the visible one wins). E.g.:
                              {"name": "Old measurement", "id": "0x0C", "hidden": true}

  Field (in tx / rx):
    Key          Values                                      Purpose
    -----------  ------------------------------------------  ---------------------------------
    name         text (REQUIRED)                             name
    label        text                                        displayed label; label_en English
    type         see below                                   data format
    count        integer >= 1                                array (raw: number of bytes)
    length       integer                                     ascii / hex / bcd: size in bytes
    unit         text                                        displayed unit
    factor       number (≠ 0)                                real value = raw × factor + offset
    offset       number
    min / max    number (real unit)                          range; null = type limits
    default      value                                       default value (request)
    decimals     integer                                     displayed decimals
    format       "ip" | "mac"                                array entry / display
    choices      {"label": value}                            choice list (decimal value or
                                                             "0xFF00")
    bits         {"bit number": "name"}                      bit field: bits at 1 are listed

  Types:
    uint8 / u8 / U8     int8 / i8        1 byte
    uint16 / u16        int16 / i16      2 bytes, protocol byte order
    uint32 / u32        int32 / i32      4 bytes, protocol byte order
    uint16be, int32le…                   byte order forced for this field
    float / f32                          IEEE 754 float, 4 bytes
    bool                                 1 byte, 0 / 1
    ascii                                text ("length" bytes, or variable when last)
    raw / hex                            raw bytes in hex ("count" bytes, or variable)
    bcd                                  decimal digits, 2 per byte ("length", default 4)
    enum                                 older way to write a choice ("size" + "choices")
    U8[4], F32[2]…                       array written in the type (= "count")


-----------------------------------------------------------------------------------------------
 13. COMPLETE EXAMPLES
-----------------------------------------------------------------------------------------------

  Example 1: minimal protocol (sync, sequence number, command, length, data, CRC16)

    {
      "name": "Example",
      "byte_order": "big",
      "tx": [
        {"name": "SYNC", "size": 2, "role": "value", "value": "0xAA55", "color": "hdr"},
        {"name": "SEQ",  "size": 1, "role": "request_id", "color": "hdr"},
        {"name": "CMD",  "size": 1, "role": "command_id", "color": "cmd"},
        {"name": "LEN",  "size": 1, "role": "length", "of": "DATA"},
        {"name": "DATA", "role": "data"},
        {"name": "CRC",  "size": 2, "role": "crc", "algo": "crc16_ccitt_false", "over": [2, "end"]}
      ],
      "rx": [
        {"name": "SYNC",   "size": 2, "role": "value", "value": "0xAA55", "color": "hdr"},
        {"name": "SEQ",    "size": 1, "role": "request_id", "color": "hdr"},
        {"name": "STATUS", "size": 1, "role": "error"},
        {"name": "LEN",    "size": 1, "role": "length", "of": "DATA"},
        {"name": "DATA",   "role": "data"},
        {"name": "CRC",    "size": 2, "role": "crc", "algo": "crc16_ccitt_false", "over": [2, "end"]}
      ],
      "errors": {"0": "OK", "1": "Unknown command"}
    }
    Request SEQ 1, CMD 2, DATA 05: AA 55 01 02 01 05 FF 80

  Example 2: Modbus command "read 2 registers" (msgLibrary/msgList/modbus/Msg_Regulateur_Exemple.json)

    {
      "name": "Lire consigne et mode", "name_en": "Read setpoint and mode",
      "id": "0x03", "group": "READ",
      "match": {"register": "0x0000"},
      "tx": [
        {"name": "register", "label_en": "Register", "type": "uint16", "default": "0x0000"},
        {"name": "quantity", "label_en": "Quantity", "type": "uint16", "default": 2}
      ],
      "rx": [
        {"name": "bytes",    "label_en": "Byte count", "type": "uint8"},
        {"name": "setpoint", "label_en": "Setpoint", "type": "int16", "factor": 0.1, "unit": "°C"},
        {"name": "mode",     "label_en": "Mode", "type": "uint16",
         "choices": {"off": 0, "auto": 1, "manual": 2}}
      ]
    }
    Request: 01 03 00 00 00 02 C4 0B      Response: 01 03 04 00 E6 00 01 DA 04
    -> Setpoint = 23.0 °C | Mode = auto (1)


-----------------------------------------------------------------------------------------------
 14. FILES PROVIDED
-----------------------------------------------------------------------------------------------

  The .json files in this folder are examples commented line by line; their list and purpose
  are in the project README. SerialHex's built-in generic protocol is described in
  core/protocol/default.py.
