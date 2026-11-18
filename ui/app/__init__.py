"""
ui/app — Fenêtre principale de SerialHex.

        ┌──────────── ComPanel (liaison série / TCP, sur 2 lignes) ─────────────┐
        ├─ [Protocole] [Manuel] ─────────────── [▶ Replay] ─┬─ ReplayPanel ─┤
        │  Manuel    : MessagesPanel │ ParamsPanel          │  (case Replay  │
        │  Protocole : ProtocolPanel                        │   cochée)      │
        ├──────────────────────────── MonitorPanel ─────────────────────────┤

Organisation (une classe App composée de plusieurs parties, une par fichier) :
    window.py     App : création des panneaux et placement
    messages.py   messages JSON de l'onglet Manuel (chargement, sélection)
    sending.py    envois, séquences, lecture des événements du port série
    protocol.py   protocole (fichier de protocols/), bibliothèque, timeout de réponse
    traces.py     enregistrement de trace, panneau Replay, flèches « → Replay »
    layout.py     disposition : séparateurs, panneau Replay affiché / masqué, fermeture
"""
from .window import App

__all__ = ["App"]
