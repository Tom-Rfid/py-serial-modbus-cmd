#!/usr/bin/env python3
"""
Génère tests/vectors.json : trames de référence calculées par core/frames.py.

Ces vecteurs servent de contrat entre l'implémentation Python et
l'implémentation TypeScript (js/) : les deux doivent produire exactement
les mêmes octets, ou échouer sur les mêmes entrées.

    python tools/gen_test_vectors.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.frames import build_frame, defaults_for, to_hex, CHECKSUMS  # noqa: E402
from core.messages import load_folder  # noqa: E402

# Tous les types entiers, pour le message synthétique ci-dessous
ALL_INTS = ["u8", "i8", "u16be", "u16le", "i16be", "i16le", "u32be", "u32le", "i32be", "i32le"]

# Message synthétique qui couvre tous les types de paramètres
ALL_TYPES = {
    "name": "Tous les types",
    "frame": ["AA 55"] + [f"{{{t}}}" for t in ALL_INTS] + ["{b}", "{e}", "{e16}", "{h}", "{a}", "{af}", "{cs}"],
    "params": {
        **{t: {"type": t, "default": 1} for t in ALL_INTS},
        "b": {"type": "bool", "default": True},
        "e": {"type": "enum", "choices": {"zero": 0, "deux": 2}},
        "e16": {"type": "enum", "size": "u16le", "choices": {"x": 0x1234}},
        "h": {"type": "hex", "default": "DE AD"},
        "a": {"type": "ascii", "default": "Hi"},
        "af": {"type": "ascii", "length": 4, "default": "ABCDEF"},
    },
    "checksum": {"algo": "xor8", "start": 2},
}

# Jeux de valeurs qui doivent produire une trame.
# {} = valeurs par défaut ; les autres testent les cas limites :
# bornes des types, signes, écritures 0x / 0b / 1_0 / 010, booléens texte,
# enum par libellé ou par nombre, ascii tronqué / complété, caractère latin-1 (é).
VALUE_SETS = [
    {},
    {"u8": 255, "i8": -128, "u16be": "0xBEEF", "u16le": "0xBEEF", "i16be": -2, "i16le": -2,
     "u32be": "0xDEADBEEF", "u32le": 4294967295, "i32be": -1, "i32le": "-0x10",
     "b": 0, "e": "deux", "h": "0x01,0x02", "a": "", "af": "Z"},
    {"u8": "0b1010", "i8": "1_0", "b": "oui", "e": "7", "h": "", "a": "é"},
    {"u8": "010"},
]

# Jeux de valeurs qui doivent provoquer une erreur dans les DEUX implémentations
# (hors limites, signe interdit, texte non numérique, hexa impair ou invalide).
ERROR_SETS = [
    {"u8": 256},
    {"i8": 128},
    {"u16be": -1},
    {"u8": "abc"},
    {"h": "ABC"},
    {"h": "GG"},
]


def case(name, msg, values):
    """Calcule un cas de test : la trame attendue, ou error=True si Python lève une erreur.

    Les valeurs par défaut sont complétées par `values` (comme le fait l'interface).
    """
    entry = {"name": name, "message": msg, "values": values}
    try:
        full = {**defaults_for(msg), **values}
        entry["frame"] = to_hex(build_frame(msg, full))
    except Exception:
        entry["error"] = True
    return entry


def main():
    """Construit tous les cas et écrit tests/vectors.json."""
    cases = []

    # 1. Les messages d'essai (tests/data/messages, communs à toutes les versions), valeurs par défaut
    messages, errors = load_folder(ROOT / "tests" / "data" / "messages")
    if errors:
        sys.exit(f"Erreur dans tests/data/messages/ : {errors}")
    for m in messages:
        cases.append(case(f"messages/{m['group']}/{m['name']}", m, {}))

    # 2. Tous les types de paramètres
    for i, vals in enumerate(VALUE_SETS):
        cases.append(case(f"types #{i}", ALL_TYPES, vals))
    for i, vals in enumerate(ERROR_SETS):
        cases.append(case(f"erreur #{i}", ALL_TYPES, vals))

    # 3. Tous les checksums, avec plusieurs points de départ
    for algo in CHECKSUMS:
        for start in (0, 2):
            msg = {"name": f"{algo} start={start}",
                   "frame": ["AA 55 01 02 03 FF 80 7F", "{cs}", "0D"],
                   "checksum": {"algo": algo, "start": start}}
            cases.append(case(f"checksum {algo} start={start}", msg, {}))

    # 4. Type raw (octets bruts, = hex) et types en majuscules
    rawmsg = {"name": "raw", "frame": ["53", "{r}", "{u}", "{cs}"],
              "params": {"r": {"type": "RAW", "default": "01 02 03"}, "u": {"type": "U16LE", "default": 258}},
              "checksum": {"algo": "crc16_modbus"}}
    cases.append(case("raw et majuscules", rawmsg, {}))

    # 5. Bornes min / max
    bounded = {"name": "bornes", "frame": ["{v}"],
               "params": {"v": {"type": "u16be", "min": 10, "max": "0x100", "default": 10}}}
    for v in (10, 256, 9, 257):
        cases.append(case(f"bornes v={v}", bounded, {"v": v}))

    out = ROOT / "tests" / "vectors.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps({"cases": cases}, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum("frame" in c for c in cases)
    print(f"{len(cases)} cas ({ok} trames, {len(cases) - ok} erreurs attendues) -> {out}")


if __name__ == "__main__":
    main()
