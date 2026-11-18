"""
core/protocol/decoded.py — Résultat du décodage d'une trame.
"""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Field:
    """Un champ décodé."""
    name: str                       # "COMMAND ID"
    start: int                      # premier octet (inclus)
    raw: bytes                      # octets du champ
    value: Optional[int] = None     # valeur numérique (None pour DATA, les CRC et les octets non lus)
    ok: Optional[bool] = None       # contrôle : True/False pour value et CRC, None sinon
    note: str = ""                  # explication, ex. "attendu 34 12", "non lu"
    role: str = "field"
    color: Optional[str] = None
    bit_start: Optional[int] = None # position du premier bit dans la trame
    bits: Optional[int] = None      # taille en bits
    meaning: str = ""               # texte de la valeur ("values" du fichier de protocole)
    description: str = ""           # description du champ (fichier de protocole)

    @property
    def span(self):
        """Position lisible : '0', '2-5' (octets), ou '1.4-2.1' (octet.bit) pour un champ en bits."""
        if self.bits is not None and self.bit_start is not None and (self.bit_start % 8 or self.bits % 8):
            first, last = self.bit_start, self.bit_start + self.bits - 1
            return f"{first // 8}.{first % 8}" + ("" if first == last else f"-{last // 8}.{last % 8}")
        end = self.start + len(self.raw) - 1
        return str(self.start) if end <= self.start else f"{self.start}-{end}"

    @property
    def hex_digits(self):
        """Nombre de chiffres hexa pour écrire la valeur : 2 par octet, ou selon le nombre de bits."""
        bits = self.bits if self.bits is not None else 8 * len(self.raw)
        return max(1, (bits + 3) // 4)


@dataclass
class Decoded:
    """Une trame décodée : ses champs, les problèmes trouvés, les octets en trop."""
    kind: str                                       # QUERY ou RESPONSE
    fields: List[Field] = field(default_factory=list)
    variant: str = ""                               # nom de la variante de trame reconnue
    encoded: bytes = b""                            # trame brute reçue, si un codage (ASCII hexa) est utilisé
    binary: bytes = b""                             # trame binaire décodée (après le codage)
    errors: List[str] = field(default_factory=list)
    complete: bool = False                          # toute la trame attendue est présente
    extra: bytes = b""                              # octets en trop après la trame

    @property
    def ok(self):
        """True si la trame est complète, sans erreur ni octet en trop."""
        return self.complete and not self.errors and not self.extra

    def get(self, name):
        """Valeur d'un champ par son nom, ou None."""
        return next((f.value for f in self.fields if f.name == name), None)

    def by_role(self, role):
        """Premier champ d'un rôle, ou None."""
        return next((f for f in self.fields if f.role == role), None)

    def _role_value(self, role):
        f = self.by_role(role)
        return f.value if f else None

    # Champs repérés par leur rôle, quel que soit leur nom dans le fichier de conf
    @property
    def request_id(self):
        return self._role_value("request_id")

    @property
    def command_id(self):
        return self._role_value("command_id")

    @property
    def error(self):
        return self._role_value("error")

    @property
    def length(self):
        return self._role_value("length")

    @property
    def data(self):
        """Champ DATA (Field), ou None s'il est absent ou vide."""
        f = self.by_role("data")
        return f if f is not None and f.raw else None

    @property
    def crc_ok(self):
        """False si un CRC est faux, True s'il y en a et qu'ils sont justes, None s'il n'y en a pas."""
        checks = [f.ok for f in self.fields if f.role == "crc"]
        return all(checks) if checks else None
