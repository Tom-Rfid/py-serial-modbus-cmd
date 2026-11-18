"""
core/commands — Bibliothèque des commandes du protocole et des codes d'erreur.

Rôle
    Décrire, dans les fichiers msgLibrary/msgList/Msg_*.json, les commandes de
    l'appareil avec :
      - une partie "tx" : les champs de DATA dans la requête (ce qu'on envoie)
      - une partie "rx" : les champs de DATA dans la réponse (ce qu'on reçoit)
      - des "presets" : jeux de valeurs prédéfinis, proposés dans un menu
    et les codes d'erreur avec leur texte ("errors").

    Chaque champ peut avoir une unité, un facteur et un offset :
        valeur physique = valeur brute × factor + offset
    Ex. puissance en 0,1 mW : brut 125  <->  12.5 mW (factor 0.1)

    Un champ peut être un tableau ("count", ex. U8[4] pour une adresse IP),
    affiché au format "ip" (192.168.1.10) ou "mac" (00:1A:2B:3C:4D:5E), et un
    entier peut être un champ de bits ("bits") : chaque bit à 1 est nommé.

Contenu
    - encode_fields()  : valeurs physiques saisies -> octets de DATA (requête)
    - decode_fields()  : octets de DATA (réponse ou requête) -> champs avec valeurs physiques
    - load_library()   : lit les commandes et les erreurs de tous les Msg_*.json
    - describe()       : résumé d'une ligne d'une trame décodée (pour le journal)

Organisation :
    types.py      types de champs, tableaux, tailles
    physical.py   facteur, offset, décimales, plages min / max
    encode.py     valeurs saisies -> octets
    decode.py     octets -> valeurs physiques (DataField)
    library.py    Command, Library, lecture des Msg_*.json
    describe.py   résumé d'une ligne pour le journal

Format JSON : voir docs/Francais/PROTOCOLE.md. Ce paquet ne dépend pas de l'interface.
"""
from .convert import input_text, int_bytes, int_text, plain_int, raw_guess, split_data
from .decode import DataField, bits_text, decode_field, decode_fields
from .describe import describe, describe_parts
from .encode import defaults, encode_field, encode_fields, split_items
from .library import (Command, Library, fits_protocol, load_library, made_for, opcode_key, parse_library_file,
                      tx_matches)
from .physical import decimals, effective_range, format_physical, parse_number, type_range
from .types import (FORMATS, INTS, OTHER_TYPES, TYPE_ALIASES, array_count, field_size, field_type,
                    is_choice, type_label)

__all__ = [
    "input_text", "int_bytes", "int_text", "plain_int", "raw_guess", "split_data",
    "DataField", "bits_text", "decode_field", "decode_fields", "describe", "describe_parts", "defaults", "encode_field",
    "encode_fields", "split_items", "Command", "Library", "fits_protocol", "load_library", "made_for", "opcode_key", "parse_library_file", "tx_matches",
    "decimals", "effective_range", "format_physical", "parse_number", "type_range", "FORMATS", "INTS",
    "OTHER_TYPES", "TYPE_ALIASES", "array_count", "field_size", "field_type", "is_choice", "type_label",
]
