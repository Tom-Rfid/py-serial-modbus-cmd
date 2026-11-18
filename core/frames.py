"""
core/frames.py — Construction des trames.

Rôle
    Transformer la définition d'un message (lue dans un Msg_*.json) et
    les valeurs saisies par l'utilisateur en une suite d'octets à envoyer.

Contenu
    - encode_param()  : convertit UNE valeur en octets selon son type (u8, u16be...)
    - checksum()      : calcule un checksum (xor8, sum8, crc16_modbus...)
    - build_frame()   : assemble la trame complète d'un message
    - defaults_for()  : valeurs par défaut des paramètres d'un message
    - outils de conversion : parse_int, parse_hex, to_hex, to_ascii

Ce module ne dépend ni de l'interface ni du port série : on peut l'utiliser
et le tester seul. Il a un équivalent TypeScript (js/src/core/frames.ts) ;
les deux doivent produire exactement les mêmes octets (tests/vectors.json).
"""
import struct

# --------------------------------------------------------------------------
# Constantes
# --------------------------------------------------------------------------

# Types entiers -> format du module struct.
#   ">" = big endian (octet de poids fort en premier)
#   "<" = little endian (octet de poids faible en premier)
#   B/b = 8 bits non signé/signé, H/h = 16 bits, I/i = 32 bits
INT_TYPES = {
    "u8": "B", "i8": "b",
    "u16be": ">H", "u16le": "<H", "i16be": ">h", "i16le": "<h",
    "u32be": ">I", "u32le": "<I", "i32be": ">i", "i32le": "<i",
}

# Valeurs considérées comme « vrai » pour un paramètre de type bool
# (comparées en minuscules : "True", "OUI", "1"... sont acceptés).
TRUTHY = ("1", "true", "on", "oui", "yes")

# Algorithmes de checksum disponibles (voir checksum()).
CHECKSUMS = ("xor8", "sum8", "sum8_2c", "crc8", "crc16_modbus")


# --------------------------------------------------------------------------
# Conversions texte -> nombre / octets
# --------------------------------------------------------------------------

def parse_int(value):
    """Convertit une saisie en entier.

    Accepte le décimal (12), l'hexa (0x0C), le binaire (0b1100), l'octal (0o14),
    les séparateurs « _ » (1_000) et les zéros en tête (010 -> 10).
    Lève ValueError si la saisie n'est pas un nombre.
    """
    s = str(value).strip().replace("_", "")
    try:
        # Base 0 : Python devine la base d'après le préfixe (0x, 0b, 0o).
        return int(s, 0)
    except ValueError:
        # La base 0 refuse « 010 » (ambigu en Python) : on le lit en décimal.
        return int(s, 10)


def parse_hex(text):
    """Convertit du texte hexa en octets.

    'AA 55', 'AA55', '0xAA,0x55' -> b'\\xaa\\x55'
    Les préfixes 0x et les virgules sont ignorés ; les espaces séparent les octets.
    Lève ValueError si le texte n'est pas de l'hexa valide.
    """
    return bytes.fromhex(str(text).replace("0x", "").replace("0X", "").replace(",", " "))


# --------------------------------------------------------------------------
# Encodage d'un paramètre
# --------------------------------------------------------------------------

def encode_param(name, pdef, value):
    """Encode la valeur d'UN paramètre en octets.

    name  : nom du paramètre (utilisé dans les messages d'erreur)
    pdef  : définition du paramètre dans le JSON, ex. {"type": "u16be", "max": 1023}
    value : valeur saisie (texte, nombre ou booléen)

    Lève ValueError avec un message lisible si la valeur est invalide.
    """
    # Type par défaut : un octet non signé. Les majuscules sont acceptées (U8, RAW).
    t = str(pdef.get("type", "u8")).lower()

    # bool : un octet, 1 si la valeur est « vraie », sinon 0
    if t == "bool":
        return bytes([1 if str(value).lower() in TRUTHY else 0])

    # enum : la valeur est un libellé de la liste "choices" (ex. "on" -> 1),
    # ou directement un nombre. Encodé sur "size" (u8 par défaut).
    if t == "enum":
        choices = pdef["choices"]
        v = choices[value] if value in choices else parse_int(value)
        return struct.pack(INT_TYPES[pdef.get("size", "u8")], v)

    # Entiers : conversion, vérification des bornes min/max, puis encodage
    if t in INT_TYPES:
        try:
            v = parse_int(value)
        except ValueError:
            raise ValueError(f"{name} : '{value}' n'est pas un nombre")
        if "min" in pdef and v < parse_int(pdef["min"]):
            raise ValueError(f"{name} : {v} < min ({pdef['min']})")
        if "max" in pdef and v > parse_int(pdef["max"]):
            raise ValueError(f"{name} : {v} > max ({pdef['max']})")
        try:
            return struct.pack(INT_TYPES[t], v)
        except struct.error:
            # Ex. 300 dans un u8 : la valeur ne tient pas dans le type
            raise ValueError(f"{name} : {v} hors limites pour {t}")

    # hex / raw : octets bruts saisis en hexa, sans conversion, longueur libre
    if t in ("hex", "raw"):
        try:
            return parse_hex(value)
        except ValueError:
            raise ValueError(f"{name} : hexa invalide")

    # ascii : texte encodé en latin-1 (1 caractère = 1 octet).
    # Avec "length", la longueur est fixe : tronqué ou complété par des 0x00.
    if t == "ascii":
        b = str(value).encode("latin-1")
        n = pdef.get("length")
        if n:
            b = b[:n].ljust(n, b"\x00")
        return b

    raise ValueError(f"{name} : type inconnu '{t}'")


# --------------------------------------------------------------------------
# Checksums
# --------------------------------------------------------------------------

def checksum(algo, data):
    """Calcule le checksum `algo` sur les octets `data`. Retourne des octets."""

    # Somme de tous les octets, on garde l'octet de poids faible
    if algo == "sum8":
        return bytes([sum(data) & 0xFF])

    # Complément à 2 de la somme : somme(data) + checksum = 0 (modulo 256)
    if algo == "sum8_2c":
        return bytes([(-sum(data)) & 0xFF])

    # OU exclusif de tous les octets
    if algo == "xor8":
        x = 0
        for b in data:
            x ^= b
        return bytes([x])

    # CRC-8 « standard » : polynôme 0x07, valeur initiale 0x00
    if algo == "crc8":
        crc = 0
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ 0x07) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
        return bytes([crc])

    # CRC-16 Modbus : polynôme 0xA001 (forme réfléchie de 0x8005), initial 0xFFFF.
    # Envoyé octet de poids faible en premier (little endian), comme le veut Modbus RTU.
    if algo == "crc16_modbus":
        crc = 0xFFFF
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
        return struct.pack("<H", crc)

    raise ValueError(f"checksum inconnu '{algo}'")


# --------------------------------------------------------------------------
# Construction d'une trame
# --------------------------------------------------------------------------

def defaults_for(msg):
    """Retourne {nom_paramètre: valeur_par_défaut} pour tous les paramètres d'un message.

    Si "default" n'est pas précisé dans le JSON :
      enum -> premier choix de la liste, hex/ascii -> vide, autres -> 0
    """
    if isinstance(msg.get("request"), dict):        # message de protocole (core/request_message.py)
        from .request_message import request_defaults
        return request_defaults(msg)
    vals = {}
    for name, pdef in msg.get("params", {}).items():
        if "default" in pdef:
            vals[name] = pdef["default"]
        elif str(pdef.get("type", "")).lower() == "enum":
            vals[name] = next(iter(pdef["choices"]))
        elif str(pdef.get("type", "")).lower() in ("hex", "raw", "ascii"):
            vals[name] = ""
        else:
            vals[name] = 0
    return vals


def build_frame(msg, values):
    """Assemble la trame d'un message.

    msg    : définition du message, ex.
             {"frame": ["AA 55", "{led}", "{cs}"], "params": {...}, "checksum": {...}}
    values : valeurs des paramètres, ex. {"led": 2}

    Chaque morceau de "frame" est soit :
      - des octets fixes en hexa  ("AA 55")
      - un paramètre              ("{led}")  -> remplacé par sa valeur encodée
      - le checksum               ("{cs}")   -> calculé à la fin
    Retourne les octets de la trame. Lève ValueError si une valeur est invalide.
    """
    if "frame" not in msg and isinstance(msg.get("request"), dict):
        raise ValueError("message de protocole : trame construite par le protocole en cours")
    out = bytearray()
    cs_pos = None                       # position où insérer le checksum

    for tok in msg["frame"]:
        tok = tok.strip()
        if tok.startswith("{") and tok.endswith("}"):
            name = tok[1:-1]
            if name == "cs":
                # On note la position : le checksum ne peut être calculé
                # qu'une fois tous les octets précédents connus.
                cs_pos = len(out)
                continue
            pdef = msg.get("params", {}).get(name)
            if pdef is None:
                raise ValueError(f"paramètre '{name}' non défini")
            out += encode_param(name, pdef, values.get(name, ""))
        else:
            out += parse_hex(tok)

    if cs_pos is not None:
        cfg = msg.get("checksum", {})
        # Le calcul porte sur les octets de "start" (inclus) jusqu'au checksum (exclu).
        # Ex. start=2 pour ne pas inclure l'en-tête AA 55.
        start = cfg.get("start", 0)
        out[cs_pos:cs_pos] = checksum(cfg.get("algo", "xor8"), bytes(out[start:cs_pos]))
    return bytes(out)


def frame_segments(msg, values):
    """Comme build_frame, mais découpe la trame en morceaux typés, pour l'affichage.

    Retourne une liste de (nature, octets), dans l'ordre de la trame :
        "fixed" : octets fixes du JSON ("AA 55")  -> affichés en gris (en-tête)
        "param" : valeur d'un paramètre ("{led}")
        "cs"    : checksum ("{cs}")               -> affiché en vert
    La concaténation des octets est identique à build_frame(msg, values).
    """
    segs = []
    cs_index = None
    for tok in msg["frame"]:
        tok = tok.strip()
        if tok.startswith("{") and tok.endswith("}"):
            name = tok[1:-1]
            if name == "cs":
                cs_index = len(segs)
                continue
            pdef = msg.get("params", {}).get(name)
            if pdef is None:
                raise ValueError(f"paramètre '{name}' non défini")
            segs.append(("param", encode_param(name, pdef, values.get(name, ""))))
        else:
            segs.append(("fixed", parse_hex(tok)))
    if cs_index is not None:
        cfg = msg.get("checksum", {})
        before = b"".join(b for _, b in segs[:cs_index])
        start = cfg.get("start", 0)
        segs.insert(cs_index, ("cs", checksum(cfg.get("algo", "xor8"), before[start:])))
    return segs


# --------------------------------------------------------------------------
# Affichage
# --------------------------------------------------------------------------

def to_hex(data):
    """b'\\xaa\\x55' -> 'AA 55'"""
    return data.hex(" ").upper()


def to_ascii(data):
    """Version texte des octets ; '.' pour les octets non imprimables."""
    return "".join(chr(b) if 32 <= b < 127 else "." for b in data)
