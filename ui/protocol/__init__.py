"""
ui/protocol — Onglet « Protocole ».

Outils autour du protocole requête / réponse (core/protocol) et de la bibliothèque
de commandes (core/commands, fichiers Msg_*.json).

    Protocole : fichier de protocols/ choisi en haut de l'onglet (mémorisé). Noms,
                tailles, CRC et couleurs des champs suivent ce fichier.
    Requête   : commande de la bibliothèque (ou saisie manuelle), formulaire des
                champs "tx", données prédéfinies, trame détaillée, Copier / Envoyer /
                « → Replay » (la trame va dans la ligne sélectionnée du replay).
    Réponse   : chaque trame reçue (ou collée) est décodée ; type de réponse Auto
                (d'après la requête envoyée), une commande, ou Brut.

Organisation : constants.py, widgets.py (FieldTable), query.py,
response.py, panel.py (ProtocolPanel).
"""
from .panel import ProtocolPanel

__all__ = ["ProtocolPanel"]
