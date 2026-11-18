"""
ui/replay — Panneau « Replay » (à droite des onglets, case « ▶ Replay ») : afficher,
modifier, enregistrer et rejouer une trace.

    1. Ouvrir une trace (ou celle qu'on vient d'arrêter, ouverte automatiquement).
       Son nom se modifie directement ; « Enregistrer » renomme le fichier (confirmation
       si le nom est déjà pris).
    2. Tableau : une ligne par ligne du fichier, TX en bleu, RX en violet. Double-clic
       sur t, Dir, Octets ou Libellé pour modifier. Cliquer une ligne affiche son détail :
       intervalle avec les lignes voisines (↑ ↓), couleurs et décodage du protocole.
    3. Remplir : « + Ajouter » (au milieu de l'intervalle avec la ligne suivante), ou les
       flèches « → Replay » des onglets Manuel et Protocole (insère après la sélection ou
       remplace la ligne sélectionnée, au choix).
    4. ▶ Rejouer : les lignes TX sont renvoyées au rythme choisi ; la ligne en cours porte
       l'icône ▶ ; résultat sur chaque ligne TX : ✓ identique, ≠ différent (fond orange),
       ✗ timeout (fond rouge), + réponse en trop (fond jaune).

Organisation : constants.py, file_bar.py, options.py, edit_bar.py, table.py, detail.py,
player.py (moteur du replay), panel.py (ReplayPanel). Les règles d'édition et de
renommage sont dans core/trace/document.py (testées sans interface).
"""
from .panel import ReplayPanel

__all__ = ["ReplayPanel"]
