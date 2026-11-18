"""
core/protocol/crc.py — CRC 8 / 16 / 32 bits et sommes simples.

Un CRC est décrit par le modèle standard des catalogues de CRC (reveng) :

    width   taille du résultat : 8, 16 ou 32 bits
    poly    polynôme, écrit en forme « normale » (ex. 0x8005 pour Modbus)
    init    valeur de départ du registre
    refin   true : chaque octet est lu bit de poids faible en premier (« réfléchi »)
    refout  true : le résultat final est réfléchi (bits inversés de bout en bout)
    xorout  valeur combinée par XOR avec le résultat final

Exemple : CRC16 Modbus = width 16, poly 0x8005, init 0xFFFF, refin et refout true,
xorout 0. Le polynôme « 0xA001 » qu'on lit souvent pour Modbus est 0x8005 réfléchi :
c'est le même calcul, écrit pour une boucle qui décale vers la droite.
"""
from dataclasses import dataclass

from .common import ProtocolError, to_int

SUM_KINDS = ("sum8", "sum8_2c", "xor8", "sum16")


def reflect(value, width):
    """Inverse l'ordre des `width` bits de poids faible de value (bit 0 <-> bit width-1)."""
    out = 0
    for _ in range(width):
        out = (out << 1) | (value & 1)
        value >>= 1
    return out


@dataclass(frozen=True)
class Crc:
    """Un algorithme de CRC, ou une somme simple (kind = "sum8", "sum8_2c", "xor8", "sum16")."""
    name: str
    width: int = 16
    poly: int = 0
    init: int = 0
    refin: bool = False
    refout: bool = False
    xorout: int = 0
    kind: str = "crc"

    @property
    def size(self):
        """Taille du résultat en octets."""
        return self.width // 8

    def compute(self, data):
        """Valeur (entier) du CRC ou de la somme des octets `data`."""
        data = bytes(data)
        if self.kind == "crc":
            return self._crc(data)
        return self._sum(data)

    def _sum(self, data):
        if self.kind == "sum8":
            return sum(data) & 0xFF
        if self.kind == "sum8_2c":                  # complément à 2 : la somme trame + checksum vaut 0
            return (-sum(data)) & 0xFF
        if self.kind == "xor8":
            result = 0
            for b in data:
                result ^= b
            return result
        if self.kind == "sum16":
            return sum(data) & 0xFFFF
        raise ValueError(f"somme inconnue : {self.kind}")

    def _crc(self, data):
        mask = (1 << self.width) - 1
        top_bit = 1 << (self.width - 1)
        register = self.init & mask
        for byte in data:
            if self.refin:
                byte = reflect(byte, 8)
            register ^= byte << (self.width - 8)     # l'octet entre par le haut du registre
            for _ in range(8):
                if register & top_bit:
                    register = ((register << 1) ^ self.poly) & mask
                else:
                    register = (register << 1) & mask
        if self.refout:
            register = reflect(register, self.width)
        return (register ^ self.xorout) & mask


# Noms prêts à l'emploi. En commentaire : compute(b"123456789"), la « valeur de
# contrôle » des catalogues, vérifiée par les tests.
CRC_PRESETS = {
    "crc16_modbus": Crc("crc16_modbus", 16, 0x8005, 0xFFFF, True, True, 0x0000),          # 0x4B37
    "crc16_ccitt_false": Crc("crc16_ccitt_false", 16, 0x1021, 0xFFFF, False, False, 0),   # 0x29B1
    "crc16_xmodem": Crc("crc16_xmodem", 16, 0x1021, 0x0000, False, False, 0),             # 0x31C3
    "crc16_kermit": Crc("crc16_kermit", 16, 0x1021, 0x0000, True, True, 0),               # 0x2189
    "crc8": Crc("crc8", 8, 0x07, 0x00, False, False, 0),                                  # 0xF4
    "crc8_maxim": Crc("crc8_maxim", 8, 0x31, 0x00, True, True, 0),                        # 0xA1
    "crc32": Crc("crc32", 32, 0x04C11DB7, 0xFFFFFFFF, True, True, 0xFFFFFFFF),            # 0xCBF43926
    "crc32_mpeg2": Crc("crc32_mpeg2", 32, 0x04C11DB7, 0xFFFFFFFF, False, False, 0),       # 0x0376E6E7
    "sum8": Crc("sum8", 8, kind="sum8"),
    "sum8_2c": Crc("sum8_2c", 8, kind="sum8_2c"),
    "xor8": Crc("xor8", 8, kind="xor8"),
    "sum16": Crc("sum16", 16, kind="sum16"),
}


def crc16_modbus(data):
    """CRC16 Modbus. Ex. 01 03 00 00 00 0A -> 0xCDC5 (envoyé C5 CD en little endian)."""
    return CRC_PRESETS["crc16_modbus"].compute(data)


def parse_crc(name, spec):
    """Une entrée de la section "crc" du fichier de conf.

    spec : nom prêt à l'emploi ("crc16_modbus"), {"preset": "..."} ou les paramètres
           {"width": 16, "poly": "0x1021", "init": 0, "refin": true, "refout": true, "xorout": 0}.
    """
    if isinstance(spec, str):
        return _preset(name, spec)
    if not isinstance(spec, dict):
        raise ProtocolError(f"crc '{name}' : nom de CRC ou objet attendu")
    if "preset" in spec:
        return parse_crc(name, spec["preset"])
    return _custom(name, spec)


def _preset(name, preset):
    if preset not in CRC_PRESETS:
        raise ProtocolError(f"crc '{name}' : '{preset}' inconnu (connus : {', '.join(CRC_PRESETS)})")
    return CRC_PRESETS[preset]


def _custom(name, spec):
    width = to_int(spec.get("width", 16), f"crc '{name}' width")
    if width not in (8, 16, 32):
        raise ProtocolError(f"crc '{name}' : width doit valoir 8, 16 ou 32")
    return Crc(name, width,
               poly=to_int(spec.get("poly", 0), f"crc '{name}' poly"),
               init=to_int(spec.get("init", 0), f"crc '{name}' init"),
               refin=bool(spec.get("refin", False)),
               refout=bool(spec.get("refout", False)),
               xorout=to_int(spec.get("xorout", 0), f"crc '{name}' xorout"))
