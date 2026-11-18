# SerialHex

> **Version Techmelec** — base open source de SerialHex, générique.

**Fichiers fournis**

| Dossier | Contenu |
|---|---|
| `protocols/` | Protocoles publics prêts à l'emploi, commentés en français et en anglais : **Modbus RTU** (`modbus_rtu.json`), **Modbus ASCII** (`modbus_ascii.json`), **Modbus TCP** (`modbus_tcp.json`), **M-Bus** (`mbus.json`), **PROFIBUS FDL** (`profibus_fdl.json`), et `exemple_generique.json`, modèle à copier |
| `msgLibrary/msgManual/` | Messages tout prêts de l'onglet Manuel : **trames Modbus RTU standard** (`Msg_Modbus.json` : fonctions 01 à 2B, CRC calculé) et démonstrations (`Msg_Divers.json`, `Msg_Sorties.json`, `Msg_Systeme.json`) |
| `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json` | **Fonctions Modbus standard** pour tout appareil (01 à 06, 07, 08, 0B, 0C, 0F, 10, 11, 14 à 18, 2B / MEI 0E), décodées champ par champ par les protocoles Modbus RTU, ASCII et TCP |
| `msgLibrary/msgList/modbus/`, `msgLibrary/msgList/mbus/`, `msgLibrary/msgList/profibus/` | Commandes d'exemple pour des appareils **fictifs** (régulateur de température, compteur d'énergie, module d'E/S) ; les commandes du régulateur visent un registre précis (`"match"`) et passent avant les fonctions standard |

Le protocole choisi au premier lancement est Modbus RTU.

Icône : `assets/icon.png` (connecteur ; source `assets/icon.svg`). Pour la changer, remplacer ce fichier par une autre image PNG.

Mini interface Python pour envoyer et recevoir des trames **hexadécimales** sur un port série (COM) ou en TCP.

Logiciel **standard** : la structure des trames d'un appareil (en-tête, tailles, CRC…) se décrit dans un fichier de protocole (`protocols/`, commentaires acceptés), et ses commandes dans des fichiers `Msg_*.json` (`msgLibrary/msgList/` ; messages seuls de l'onglet Manuel : `msgLibrary/msgManual/`). Toutes les clés possibles : [`protocols/LISEZMOI_CONF.txt`](protocols/LISEZMOI_CONF.txt). Sans fichier de protocole utilisable, un protocole générique intégré prend le relais.

La version (nom, titre de la fenêtre, icône, protocole choisi au premier lancement) est décrite dans `edition.json` ; l'icône est `assets/icon.png`, à remplacer par n'importe quelle image PNG.

Interface en **français ou en anglais** (liste de choix à droite des onglets).

![Python](https://img.shields.io/badge/python-3.9%2B-blue) ![OS](https://img.shields.io/badge/OS-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey)

## Installation

Le projet tourne dans un **environnement virtuel** (`.venv`) avec **Python 3.9** : il n'interfère pas avec les autres versions de Python installées sur la machine.

> Python 3.9 est le minimum du débogueur de VS Code (extension *Python Debugger*). Le code reste compatible Python 3.8 (pas de `match / case`, pas de `list[int]`…) : SerialHex tourne toujours en 3.8 si une machine l'impose, seul le débogage demande 3.9.

### 1. Installer Python 3.9

Télécharger l'installeur Windows 64 bits de Python 3.9 (3.9.13, dernier installeur Windows de la 3.9) sur [python.org](https://www.python.org/downloads/windows/).

À l'installation, garder **« py launcher »** et **« tcl/tk and IDLE »** cochés. « Add Python to PATH » n'est pas nécessaire.

> Plusieurs versions de Python peuvent être installées côte à côte (3.8, 3.9, 3.12…) : chacune a son dossier, et le lanceur `py` permet de choisir. Vérifier avec `py --list`.

### 2. Récupérer le projet

```bash
git clone https://github.com/<compte>/GUI_PyCommSerial.git
cd GUI_PyCommSerial
```

### 3. Préparer l'environnement

**Automatique (Windows)** : double-cliquer sur **`setup.bat`**.

Le script :

1. vérifie que Python 3.9 est installé ;
2. crée l'environnement virtuel `.venv` (ou le recrée si sa version de Python a changé) ;
3. met `pip` à jour et installe `requirements.txt` ;
4. vérifie que tkinter et pyserial se chargent, puis lance les tests.

Options, depuis un terminal :

```powershell
.\setup.bat -Python 3.12    # utiliser une autre version de Python
.\setup.bat -Recreate       # supprimer .venv et repartir de zéro
```

**Dans VS Code**, après le setup (et après chaque changement de version de Python) :

1. `Ctrl+Shift+P` → **Python: Select Interpreter** → `.venv` (VS Code garde en mémoire l'interpréteur choisi : il ne bascule pas tout seul sur le nouveau `.venv`) ;
2. **Terminal → Tuer tous les terminaux**, puis **Terminal → Nouveau terminal** : l'invite commence par `(.venv)` (profil « PowerShell (.venv) » de `.vscode/settings.json`, qui lance `Activate.ps1` au démarrage du terminal).

Fermer VS Code avant un `setup.bat -Recreate` : l'extension Python garde `python.exe` du `.venv` ouvert, et sa suppression échoue.

**Manuel (Windows)** : les mêmes étapes, à la main.

```powershell
py --list                                 # versions installées
py -3.9 -m venv .venv                     # crée l'environnement
.venv\Scripts\python -m pip install --upgrade pip
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m unittest discover tests
```

**Manuel (Linux / macOS)**

```bash
sudo apt install python3-tk               # Debian / Ubuntu : Tkinter
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

## Lancer

**Automatique (Windows)** : double-cliquer sur **`run.bat`**.

**Manuel** :

```powershell
.venv\Scripts\python serialhex.py         # Windows
.venv/bin/python serialhex.py             # Linux / macOS
```

Pour taper simplement `python` et `pip` dans le terminal, activer l'environnement :

```powershell
.venv\Scripts\Activate.ps1                # Windows (PowerShell)
source .venv/bin/activate                 # Linux / macOS
```

> Si PowerShell refuse d'exécuter le script d'activation : `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (une seule fois).

## VS Code

Le dossier `.vscode/` est fourni. À l'ouverture du projet, accepter l'installation des extensions proposées (Python, Python Debugger), puis préparer le `.venv` une fois (`setup.bat`, ou la tâche « Environnement : préparer .venv »).

| Action | Raccourci / menu |
|---|---|
| Lancer l'interface | **Ctrl+Shift+B** (tâche « SerialHex : lancer ») |
| Déboguer l'interface (points d'arrêt, variables) | **F5**, configuration « SerialHex : interface (debug) » |
| Lancer comme `run.bat` | Ctrl+Shift+P → « Tâches : Exécuter la tâche » → « SerialHex : lancer via run.bat » |
| Tests Python | Panneau **Tests** (fiole), ou F5 « Tests Python (debug) » |
| Terminal hexa | F5 « Terminal hexa (tools/hexterm.py) » : port et vitesse demandés au lancement |

Les configurations utilisent l'interpréteur du `.venv`. Si VS Code en propose un autre : Ctrl+Shift+P → « Python : Sélectionner l'interpréteur » → `.venv`.

## Documentation

Documentation en français dans [docs/Francais/](docs/Francais/), en anglais dans [docs/English/](docs/English/).

| Français | English | Contenu |
|---|---|---|
| [GUI.md](docs/Francais/GUI.md) | [GUI.md](docs/English/GUI.md) | Utilisation de l'interface : liaison série, messages, moniteur, dépannage |
| [MESSAGES.md](docs/Francais/MESSAGES.md) | [MESSAGES.md](docs/English/MESSAGES.md) | Écrire ses fichiers de messages : trames, paramètres, checksums, fusion |
| [TRACE.md](docs/Francais/TRACE.md) | [TRACE.md](docs/English/TRACE.md) | Enregistrer une trace des échanges, la modifier dans le panneau Replay et la rejouer en comparant les réponses |
| [PROTOCOLE.md](docs/Francais/PROTOCOLE.md) | [PROTOCOL.md](docs/English/PROTOCOL.md) | Protocole requête / réponse : fichier de protocole, bibliothèque de commandes, onglet Protocole |
| [CONF_PROTOCOLE.md](docs/Francais/CONF_PROTOCOLE.md) | [CONF_PROTOCOL.md](docs/English/CONF_PROTOCOL.md) | **Toutes les options du fichier de protocole**, avec descriptions et exemples (rôles, tailles, bits, variantes de trame, codage ASCII, CRC 8/16/32, textes lisibles) |
| [LISEZMOI_CONF.txt](protocols/LISEZMOI_CONF.txt) | [README_CONF.txt](protocols/README_CONF.txt) | Aide-mémoire en texte simple : structure, toutes les clés et valeurs possibles, exemples |
| [ARCHITECTURE.md](docs/Francais/ARCHITECTURE.md) | [ARCHITECTURE.md](docs/English/ARCHITECTURE.md) | Organisation du code et rôle de chaque module |
| [INTERFACE.md](docs/Francais/INTERFACE.md) | [INTERFACE.md](docs/English/INTERFACE.md) | S'interfacer avec SerialHex depuis une autre application (Electron / React) : contrat, API, protocole IPC |

Le dossier [Claude_IA/](Claude_IA/) contient les consignes pour Claude (`CLAUDE.md`) et l'état du projet (`STATUS.md`).

## Licence

MIT, voir [LICENSE](LICENSE).
