#!/usr/bin/env python3
"""
SerialHex — envoi / réception de trames hexa sur port série.

Point d'entrée du programme.

    python serialhex.py           lance l'interface graphique
    python serialhex.py --merge   fusionne msgLibrary/msgManual/Msg_*.json -> messages_merged.json

Organisation du code :
    core/   logique (trames, messages, port série, réglages), sans interface
    ui/     interface Tkinter, un fichier par panneau
    Voir docs/Francais/ARCHITECTURE.md
"""
import sys
from pathlib import Path

# Dossier du projet : tous les chemins (msgLibrary/, settings.json) en dépendent,
# quel que soit le dossier depuis lequel le script est lancé.
BASE_DIR = Path(__file__).resolve().parent
# Permet « import core... » / « import ui... » même lancé depuis un autre dossier
sys.path.insert(0, str(BASE_DIR))


def merge():
    """Option --merge : regroupe tous les fichiers de messages en un seul."""
    from core.messages import merge_files
    out = BASE_DIR / "messages_merged.json"
    try:
        n = merge_files(BASE_DIR / "msgLibrary" / "msgManual", out)
    except ValueError as e:
        print(f"Erreur : {e}")
        sys.exit(1)
    print(f"{n} message(s) fusionné(s) dans {out}")


def main():
    if "--merge" in sys.argv:
        merge()
        return
    # Vérifie pyserial avant de charger l'interface, pour un message clair
    try:
        import serial  # noqa: F401  (import utilisé uniquement pour le test)
    except ImportError:
        print("pyserial n'est pas installé :  pip install -r requirements.txt")
        sys.exit(1)
    # Langue de l'interface (settings.json) : à choisir AVANT d'importer les panneaux,
    # dont certains libellés sont calculés à l'import (voir ui/i18n.py).
    from core.settings import Settings
    from ui.i18n import set_language
    set_language(Settings(BASE_DIR / "settings.json")["language"])
    # Import ici (et pas en haut du fichier) : l'option --merge fonctionne
    # même sans Tkinter installé.
    from ui.app import App
    from core.edition import load_edition
    from ui.icon import set_windows_app_id
    # Windows : identifiant propre (avant la fenêtre), pour que la barre des tâches montre
    # l'icône de SerialHex et pas celle de Python
    set_windows_app_id("SerialHex." + (load_edition(BASE_DIR)["name"] or "SerialHex").replace(" ", ""))
    App(BASE_DIR).mainloop()        # mainloop() rend la main à la fermeture de la fenêtre


if __name__ == "__main__":
    main()
