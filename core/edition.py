"""
core/edition.py — Version du logiciel : fichier edition.json à la racine du projet.

Le code est le même pour toutes les versions ; seuls changent edition.json, l'icône
(assets/) et les fichiers de protocols/ et msgLibrary/. Exemple :

    {
      "name": "Techmelec",                   // éditeur / version
      "title": "SerialHex",                  // titre de la fenêtre
      "default_protocol": "modbus_rtu.json", // protocole choisi au premier lancement
      "icon": "assets/icon.png",             // icône de la fenêtre (PNG), relative au projet
      "url": "https://github.com/…",         // lien affiché dans « À propos » (facultatif)
      "ports": {                             // liste des ports série du panneau Liaison
        "hide_bluetooth": true,              //   ports série sur Bluetooth jamais affichés
        "filter_label": "FTDI",              //   texte de la case de filtre
        "filter_default": false,             //   case cochée au premier lancement (mémorisée ensuite)
        "filter": [                          //   adaptateurs gardés quand la case est cochée ;
          {"name": "FT232R", "vid": "0x0403", "pid": "0x6001", "enabled": true},   // "enabled": false
          …                                  //   pour en retirer un sans effacer la ligne
        ]
      }
    }

Fichier absent ou illisible : valeurs par défaut ci-dessous.
"""
from pathlib import Path

from .jsonc import load_file
from .port_filter import DEFAULT_PORT_FILTER

# Liste des ports série : valeurs par défaut de la clé "ports"
PORTS_DEFAULTS = {
    "hide_bluetooth": True,
    "filter_label": "FTDI",
    "filter_default": False,
    "filter": DEFAULT_PORT_FILTER,
}

DEFAULTS = {
    "name": "",
    "title": "SerialHex",
    "default_protocol": "",
    "icon": "assets/icon.png",
    "url": "",
    "ports": PORTS_DEFAULTS,
}


def load_edition(base_dir):
    """Réglages de la version (dict complété par DEFAULTS)."""
    edition = dict(DEFAULTS)
    try:
        data = load_file(Path(base_dir) / "edition.json")
    except (OSError, ValueError):
        return edition
    if isinstance(data, dict):
        edition.update({k: v for k, v in data.items() if k in DEFAULTS and v is not None})
    return edition


def window_title(edition):
    """« SerialHex — Techmelec », ou « SerialHex » sans nom de version."""
    return f"{edition['title']} — {edition['name']}" if edition["name"] else edition["title"]


def port_options(edition):
    """Clé "ports" d'une édition, complétée par PORTS_DEFAULTS (clés absentes ou à null)."""
    options = dict(PORTS_DEFAULTS)
    given = edition.get("ports")
    if isinstance(given, dict):
        options.update({k: v for k, v in given.items() if k in PORTS_DEFAULTS and v is not None})
    return options
