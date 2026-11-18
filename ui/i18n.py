"""
ui/i18n.py — Langue de l'interface : français (langue du code) ou anglais.

Les textes sont écrits en français dans le code et passent par _() :

    ttk.Button(row, text=_("Envoyer"))                       -> "Send" en anglais
    _("Connecté : {0}").format(link.describe())              -> "Connected: COM3 @ 115200 8N1"

Les traductions sont dans ui/lang/en.json (fichier modifiable, une ligne par texte) :
    "strings"  : {"texte français": "English text"}
    "patterns" : messages construits par core/ (décodage des trames, erreurs de connexion…),
                 traduits par tr() d'après un modèle : {"fr": "^(.+) incorrect$", "en": "{1} wrong"}

La langue se choisit au démarrage (réglage "language" de settings.json, liste « Langue »
de la fenêtre) : set_language() doit être appelée AVANT d'importer les panneaux, dont
certains libellés sont calculés à l'import. Changer de langue relance SerialHex.
Un texte absent du fichier reste en français.
"""
import json
import re
from pathlib import Path

LANGUAGES = {"fr": "Français", "en": "English"}
LANG_DIR = Path(__file__).resolve().parent / "lang"

_state = {"lang": "fr", "strings": {}, "patterns": []}


def set_language(code):
    """Choisit la langue ("fr" ou "en"). Une langue inconnue ou un fichier illisible : français."""
    _state.update(lang="fr", strings={}, patterns=[])
    if code == "fr" or code not in LANGUAGES:
        return
    try:
        data = json.loads((LANG_DIR / f"{code}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    _state["lang"] = code
    _state["strings"] = dict(data.get("strings") or {})
    _state["patterns"] = [(re.compile(p["fr"], re.S), p["en"]) for p in data.get("patterns") or []]


def language():
    return _state["lang"]


def _(text):
    """Texte de l'interface dans la langue choisie."""
    if _state["lang"] == "fr":
        return text
    return _state["strings"].get(text, text)


def tr(text, depth=0):
    """Message construit par core/ (ex. « CRC incorrect », « COM3 déjà utilisé… »),
    traduit d'après les modèles du fichier de langue. Les morceaux séparés par « · » ou « , »
    sont traduits un par un. Inchangé si rien ne correspond."""
    if _state["lang"] == "fr" or not isinstance(text, str) or not text or depth > 4:
        return text
    if text in _state["strings"]:
        return _state["strings"][text]
    for rx, template in _state["patterns"]:
        m = rx.fullmatch(text)
        if m:
            groups = [""] + [tr(g, depth + 1) if g else "" for g in m.groups()]
            return template.format(*groups)
    for sep in (" · ", ", ", " ; "):
        if sep in text:
            return sep.join(tr(part, depth + 1) for part in text.split(sep))
    return text
