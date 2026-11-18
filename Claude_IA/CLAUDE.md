# CLAUDE.md — SerialHex

> Consignes pour Claude (et tout assistant IA) qui travaille sur ce dépôt. État : [STATUS.md](STATUS.md).

## Le projet

SerialHex : envoi / réception de trames hexa sur port série ou TCP (Python / Tkinter), plus un paquet TypeScript (`js/`, npm `serialhex`) pour l'intégrer dans une application Electron / React. Version **Techmelec**, open source et **générique** : les protocoles fournis sont publics (Modbus RTU / ASCII / TCP, M-Bus, PROFIBUS FDL) et les appareils d'exemple sont fictifs.

## Règles

1. Rester générique : pas de protocole ni de commandes propres à un client ou à un produit.
2. Un protocole se décrit dans un fichier JSON de `protocols/` (voir `docs/Francais/CONF_PROTOCOLE.md`) ; le moteur (`core/protocol/`) ne doit pas contenir de cas particulier pour un appareil.
3. Onglet Manuel : seulement les messages présents dans des fichiers ; pas de messages générés automatiquement.
4. Toute modification de format doit garder Python (`core/`) et TypeScript (`js/src/core/`) identiques (vecteurs de test partagés).

## Où mettre quoi

| Sujet | Emplacement |
|---|---|
| Logique sans interface | `core/` (trames, messages, protocole, commandes, trace, liaisons) |
| Interface Tkinter | `ui/` (un fichier par panneau ; gros panneaux en paquets : `ui/app/`, `ui/protocol/`, `ui/replay/`) |
| Paquet TypeScript | `js/src/` (même format et même moteur de protocole que `core/`) |
| Traductions anglaises de l'interface | `ui/lang/en.json` : **chaque** texte `_("…")` doit y être, sinon `tests/test_i18n.py` échoue |
| Documentation | `docs/Francais/` et `docs/English/` : mettre à jour **les deux** |

Conventions : commentaires et docstrings en français, fonctions courtes, un fichier par sujet. Voir `docs/Francais/ARCHITECTURE.md`.

## Tests

```
python -m pytest -q
cd js && npm test
```

- Après une modification de `core/frames.py` ou `core/protocol/` : `python tools/gen_test_vectors.py` et `python tools/gen_protocol_vectors.py`, puis les tests Python **et** TypeScript (vecteurs partagés).
- Interface : tests sous écran virtuel (`xvfb-run python …`) avec un port série simulé ; vérifier aussi l'affichage.
