"""
core/protocol/protocol.py — Un protocole décrit par un fichier de configuration.

    p = Protocol(conf)                       # conf : contenu du fichier JSON (dict)
    frame = p.build_query(5, 0x00000004, b"\\x01")
    d = p.decode(frame, QUERY)
    d.request_id, d.command_id, d.data.raw, d.ok, d.variant

Variantes de trame : "tx" / "rx" peuvent décrire plusieurs formats, reconnus à leurs
octets fixes (M-Bus : E5 / 10… / 68…, Profibus : SD1 à SD4) :

    "rx": {"variants": [ {"name": "Accusé", "fields": [...]}, {"name": "Long", "fields": [...]} ]}

Un Protocol expose aussi byte_order, pack() et unpack() : il peut être passé
partout où un ordre des octets est attendu (core.commands).
"""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

from .bits import is_byte_aligned, read_bits
from .builder import build_frame
from .common import KIND_KEYS, QUERY, RESPONSE, ProtocolError, to_int
from .crc import Crc, parse_crc
from .decoder import decode_frame
from .encoding import parse_encoding
from .fields import FieldSpec, check_layout, check_unique_names, parse_field, value_text
from .placement import order_fields


@dataclass
class Variant:
    """Un format de trame : son nom (vide s'il n'y en a qu'un) et ses champs."""
    name: str
    fields: List[FieldSpec] = field(default_factory=list)
    description: str = ""
    description_en: str = ""


class Protocol:
    def __init__(self, conf, path=None):
        if not isinstance(conf, dict):
            raise ProtocolError("le fichier doit contenir un objet JSON")
        self.conf = conf
        self.path = Path(path) if path else None
        self.language = "fr"                    # langue des textes ("values", descriptions)
        self.name = str(conf.get("name") or (self.path.stem if self.path else "protocole"))
        self.description = str(conf.get("description") or "")
        self.description_en = str(conf.get("description_en") or "")
        self.byte_order = self._read_byte_order(conf)
        self.bit_order = self._read_bit_order(conf)
        self.encoding = parse_encoding(conf)
        self.crcs: Dict[str, Crc] = self._read_crcs(conf)
        self.variants: Dict[str, List[Variant]] = {kind: self._read_variants(conf, kind) for kind in (QUERY, RESPONSE)}
        self.layouts = {kind: variants[0].fields for kind, variants in self.variants.items()}
        self.commands_dir = self._read_commands_dir(conf)
        self.errors = {to_int(k, "errors"): v for k, v in (conf.get("errors") or {}).items()}
        self.categories = dict(conf.get("categories") or {})

    def __repr__(self):
        return f"Protocol({self.name!r})"

    # ------------------------------------------------------------------
    # Lecture du fichier de conf
    # ------------------------------------------------------------------
    @staticmethod
    def _read_byte_order(conf):
        order = conf.get("byte_order", "little")
        if order not in ("little", "big"):
            raise ProtocolError("byte_order doit valoir little ou big")
        return order

    @staticmethod
    def _read_bit_order(conf):
        """Sens de lecture des bits d'un octet pour les champs en bits (voir bits.py)."""
        order = conf.get("bit_order", "msb")
        if order not in ("msb", "lsb"):
            raise ProtocolError("bit_order doit valoir msb ou lsb")
        return order

    @staticmethod
    def _read_crcs(conf):
        section = conf.get("crc") or {}
        if not isinstance(section, dict):
            raise ProtocolError("\"crc\" doit être un objet {nom: définition}")
        return {name: parse_crc(name, spec) for name, spec in section.items()}

    def _read_variants(self, conf, kind):
        """"tx" / "rx" : une liste de champs, ou {"variants": [{"name", "fields"}, ...]}."""
        key = KIND_KEYS[kind]
        items = conf.get(key)
        if isinstance(items, dict) and "variants" in items:
            return self._read_variant_list(items["variants"], key)
        return [Variant("", self._read_fields(items, key))]

    def _read_variant_list(self, variants, key):
        if not isinstance(variants, list) or not variants:
            raise ProtocolError(f"\"{key}\" : variants doit être une liste de formats de trame")
        out = []
        for v in variants:
            if not isinstance(v, dict) or not v.get("name"):
                raise ProtocolError(f"\"{key}\" : chaque variante doit avoir un \"name\"")
            where = f"{key} [{v['name']}]"
            out.append(Variant(str(v["name"]), self._read_fields(v.get("fields"), where),
                               str(v.get("description") or ""), str(v.get("description_en") or "")))
        names = [v.name for v in out]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ProtocolError(f"\"{key}\" : variantes en double : {', '.join(duplicates)}")
        return out

    def _read_fields(self, items, where):
        if not isinstance(items, list) or not items:
            raise ProtocolError(f"\"{where}\" : liste de champs attendue")
        fields = [parse_field(d, self.crcs, where) for d in items]
        check_unique_names(fields, where)       # avant le placement, qui s'appuie sur les noms
        fields = order_fields(fields, where)    # "at" / "after" : ordre final des octets
        check_layout(fields, where)
        return fields

    def _read_commands_dir(self, conf):
        """Dossier des commandes Msg_*.json, relatif au fichier de protocole ; None si absent."""
        commands = conf.get("commands")
        if not commands:
            return None
        base = self.path.parent if self.path else Path(".")
        return (base / commands).resolve()

    # ------------------------------------------------------------------
    # Ordre des octets (compatibilité avec core.commands)
    # ------------------------------------------------------------------
    def pack(self, value, size, order=None):
        return value.to_bytes(size, order or self.byte_order)

    def unpack(self, raw, order=None):
        return int.from_bytes(raw, order or self.byte_order)

    # ------------------------------------------------------------------
    # Informations
    # ------------------------------------------------------------------
    def variant_names(self, kind):
        """Noms des variantes de trame (liste vide s'il n'y a qu'un format)."""
        names = [v.name for v in self.variants[kind]]
        return names if len(names) > 1 or names[0] else []

    def layout(self, kind, variant=None):
        """Champs d'une variante (par son nom) ; la première si variant est vide."""
        if not variant:
            return self.layouts[kind]
        for v in self.variants[kind]:
            if v.name == variant:
                return v.fields
        raise ValueError(f"variante de trame inconnue : {variant}")

    def field(self, kind, name):
        """Champ par son nom (FieldSpec), cherché dans toutes les variantes."""
        for v in self.variants[kind]:
            for f in v.fields:
                if f.name == name:
                    return f
        raise KeyError(name)

    def spec(self, kind, role):
        """Champ d'un rôle (FieldSpec) dans la première variante qui en a un, ou None."""
        for v in self.variants[kind]:
            found = next((f for f in v.fields if f.role == role and f.present), None)
            if found:
                return found
        return None

    def has(self, kind, role):
        return self.spec(kind, role) is not None

    def max_value(self, kind, role):
        """Valeur maximale d'un champ (255 pour un REQUEST ID sur 1 octet), ou None."""
        f = self.spec(kind, role)
        return None if f is None else (1 << f.bits) - 1

    @property
    def main_crc(self):
        """CRC « principal » (premier champ CRC des requêtes) et son ordre d'octets : sert à « Calc auto CRC »."""
        f = self.spec(QUERY, "crc")
        if f is None:
            return None, self.byte_order
        return f.algo, f.order or self.byte_order

    def crc_bytes(self, data):
        """CRC principal de `data`, en octets (vide si le protocole n'a pas de CRC)."""
        algo, order = self.main_crc
        return algo.compute(data).to_bytes(algo.size, order) if algo else b""

    @property
    def frame_end(self):
        """Délimiteur de fin de trame sur la ligne (Modbus ASCII : CR LF), ou None."""
        return self.encoding.end if self.encoding is not None and self.encoding.end else None

    def text(self, texts, value):
        """Texte d'une valeur dans une table {valeur: texte ou {"fr", "en"}}, dans la langue choisie."""
        return value_text(texts, value, self.language)

    def error_texts(self):
        """Codes d'erreur du fichier : {code: texte} dans la langue choisie."""
        return {code: self.text(self.errors, code) for code in self.errors}

    def category_text(self, code):
        """Texte d'une catégorie ("categories" du fichier), ou le code lui-même."""
        if code in self.categories:
            return value_text({0: self.categories[code]}, 0, self.language) or code
        return code

    # ------------------------------------------------------------------
    # Trames
    # ------------------------------------------------------------------
    def matches(self, frame, kind):
        """True si la trame commence comme ce protocole (octets fixes du début d'une variante).
        Un protocole sans octet fixe accepte toutes les trames."""
        frame = bytes(frame)
        if not frame:
            return False
        if self.encoding is not None:
            ok, frame = self.encoding.prefix(frame)
            if not ok:
                return False
            if not frame:
                return True
        return any(self._layout_matches(frame, v.fields) for v in self.variants[kind])

    def _layout_matches(self, frame, layout):
        cursor = 0                              # en bits
        for f in layout:
            if not f.present:
                continue
            if f.bits is None or f.cond:
                break                           # position des champs suivants inconnue
            if f.role == "value" and not self._fixed_matches(frame, f, cursor):
                return False
            cursor += f.bits
        return True

    def _fixed_matches(self, frame, f, cursor):
        """Octet(s) fixe(s) à la bonne valeur ; une trame trop courte est comparée sur ce qu'elle a."""
        if is_byte_aligned(cursor, f.bits):
            start = cursor // 8
            raw = frame[start:start + f.bits // 8]
            return not raw or raw == self.pack(f.value, f.bits // 8, f.order)[:len(raw)]
        if (cursor + f.bits + 7) // 8 > len(frame):
            return True
        return read_bits(frame, cursor, f.bits, self.bit_order) == f.value

    def build(self, kind, data=b"", values=None, variant=None, **kw):
        """Trame complète. values (ou arguments nommés) : {rôle ou nom de champ: valeur}.
        variant : nom de la variante de trame (la première par défaut)."""
        binary = build_frame(self, self.layout(kind, variant), data, dict(values or {}, **kw))
        return self.encoding.wrap(binary) if self.encoding is not None else binary

    def build_query(self, request_id=0, command_id=0, data=b""):
        return self.build(QUERY, data, request_id=request_id, command_id=command_id)

    def build_response(self, request_id=0, error=0, data=b""):
        return self.build(RESPONSE, data, request_id=request_id, error=error)

    def decode(self, frame, kind):
        """Décode une trame (variante reconnue à ses octets fixes). Ne lève jamais d'erreur."""
        frame = bytes(frame)
        if self.encoding is None:
            return self._decode_binary(frame, kind)
        binary, problems, complete, extra = self.encoding.unwrap(frame)
        d = self._decode_binary(binary, kind)
        d.errors = problems + d.errors
        d.complete = d.complete and complete
        d.extra = d.extra + extra
        d.encoded, d.binary = frame, binary
        return d

    def _decode_binary(self, frame, kind):
        candidates = [v for v in self.variants[kind] if self._layout_matches(frame, v.fields)]
        candidates = candidates or self.variants[kind][:1]
        first = None
        for v in candidates:
            d = decode_frame(self, v.fields, kind, frame)
            d.variant = v.name
            if d.ok:
                return d
            first = first or d
        return first

    def display_segments(self, decoded, segments):
        """Couleurs à appliquer à la trame telle qu'elle passe sur la ligne (codage ASCII compris)."""
        if self.encoding is None or not decoded.encoded:
            return segments
        return self.encoding.raw_segments(segments, len(decoded.binary))
