"""
core/settings.py — Réglages mémorisés entre deux lancements.

Les réglages (dernier port utilisé, vitesse, format, délai de fin de trame)
sont enregistrés dans settings.json, à côté de serialhex.py.
Ce fichier est propre à chaque poste : il est exclu de Git (.gitignore).
"""
import json
from pathlib import Path

# Valeurs utilisées au premier lancement, ou si settings.json est absent / illisible.
DEFAULTS = {
    "port": "",           # dernier port connecté, ex. "COM3"
    "baudrate": 115200,   # vitesse en bauds
    "bytesize": 8,        # bits de données : 5, 6, 7 ou 8
    "parity": "N",        # N = aucune, E = paire, O = impaire, M = mark, S = space
    "stopbits": "1",      # "1", "1.5" ou "2" (texte, pour garder "1.5" exact)
    "flow": "none",       # contrôle de flux : none, rtscts, xonxoff
    "gap_ms": 20,         # silence (ms) qui marque la fin d'une trame reçue
    "rx_timeout_ms": 500, # délai max entre une requête du protocole et sa réponse
    # Protocole requête / réponse : fichier de conf du dossier protocols/ (core/protocol/).
    # Vide : celui de edition.json ("default_protocol"), sinon le premier fichier du dossier.
    "protocol": "",
    "replay_visible": False,  # panneau Replay affiché à droite des onglets
    "colors": {},             # couleurs réglées dans la page « Couleurs… » (ui/theme.py)
    "decode_protocol": True,  # résumé du protocole à côté des trames dans le moniteur
    "auto_connect": False,    # se reconnecter au dernier port au démarrage
    "port_filter": None,      # case de filtre des ports (« FTDI ») cochée ; None = choix de edition.json
    "link": "serial",         # liaison : "serial" (port série) ou "tcp" (Modbus TCP, passerelle)
    "tcp_host": "192.168.1.10",   # adresse du serveur TCP
    "tcp_port": 502,          # port TCP (502 = Modbus TCP)
    "language": "fr",         # langue de l'interface : "fr" ou "en"
    "show_hidden_commands": False,
    "favorite_commands": {},  # onglet Protocole : commandes favorites, par protocole {nom: [libellés]}
    # Onglet Manuel : fichiers de messages ajoutés (Charger…, Sauvegarder… hors de msgLibrary/msgManual/),
    # chemins absolus ; relus à chaque lancement et par Recharger, en plus du dossier msgLibrary/msgManual/
    "message_files": [],  # onglet Protocole : afficher aussi les commandes masquées ("hidden")
    # Disposition de la fenêtre (taille, séparateurs), retrouvée au lancement suivant
    "geometry": "",
    "zoomed": False,
    "sashes": {},
    # Version de la disposition par défaut : si elle change (nouvelle disposition), la taille
    # et les séparateurs mémorisés sont oubliés une fois (ui/app/layout.py, LAYOUT_VERSION)
    "layout_version": 0,
}


class Settings(dict):
    """Dictionnaire des réglages, avec chargement / sauvegarde dans un fichier JSON.

    S'utilise comme un dict normal :
        settings["baudrate"] = 9600
        settings.save()
    """

    def __init__(self, path):
        super().__init__(DEFAULTS)      # on part des valeurs par défaut
        self.path = Path(path)
        self.load()                     # puis on applique le fichier s'il existe

    def load(self):
        """Lit le fichier. Les clés inconnues sont ignorées, les erreurs aussi."""
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return                      # fichier absent ou corrompu : valeurs par défaut
        self.update({k: v for k, v in data.items() if k in DEFAULTS})

    def save(self):
        """Écrit le fichier. Une erreur d'écriture (dossier en lecture seule...) est ignorée."""
        try:
            self.path.write_text(json.dumps(dict(self), indent=2), encoding="utf-8")
        except OSError:
            pass
