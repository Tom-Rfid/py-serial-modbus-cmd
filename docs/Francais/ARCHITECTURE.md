# Architecture

[← Retour au README](../../README.md)

## Arborescence

```
serialhex.py               point d'entrée (lancement, option --merge)
requirements.txt
setup.bat / setup.ps1      prépare l'environnement .venv (Python 3.9 par défaut)
run.bat                    lance SerialHex avec .venv
core/                      logique, sans interface graphique
  frames.py                construction des trames des messages libres, checksums
  messages.py              chargement / fusion des Msg_*.json, doublons
  request_message.py       messages « de protocole » (clé "request"), sauvegarde depuis l'onglet Protocole
  jsonc.py                 lecture JSON avec commentaires (// et /* */)
  framing.py               découpage des octets reçus en trames (silence, délimiteur de fin)
  serial_link.py           ports, test de disponibilité, connexion, lecture
  port_filter.py           filtre des ports (VID / PID, FTDI), masquage Bluetooth
  tcp_link.py              liaison TCP (Modbus TCP, passerelles), même interface que SerialLink
  link_switch.py           liaison série OU TCP, vue comme une seule liaison
  settings.py              réglages persistants (settings.json)
  edition.py               lecture de edition.json (version du logiciel)
  protocol/                moteur de protocole, piloté par protocols/*.json
    common.py              QUERY, RESPONSE, ProtocolError
    crc.py                 CRC 8 / 16 / 32 bits et sommes
    fields.py              description d'un champ, vérifications du fichier
    placement.py           ordre final des champs : "at" (octet, start, end), "after"
    bits.py                lecture / écriture de champs en bits (LENb, atb, bit_order)
    encoding.py            codage sur la ligne (Modbus ASCII : « :0103…\r\n »)
    decoded.py             résultat d'un décodage (Field, Decoded)
    builder.py             construction d'une trame
    decoder.py             décodage d'une trame
    protocol.py            classe Protocol, variantes de trame (M-Bus, PROFIBUS)
    loader.py              lecture des fichiers de protocols/
    default.py             protocole générique intégré (repli)
    helpers.py             raccourcis, couleurs, résumé
  commands/                bibliothèque de commandes (Msg_*.json : "commands", "errors")
    types.py               types de champs, tableaux, tailles
    physical.py            facteur, offset, décimales, min / max
    encode.py / decode.py  valeurs ↔ octets
    convert.py             DATA brute ↔ texte de saisie, entier, lectures possibles (raw_guess)
    library.py             Command, Library, lecture des fichiers, clé "protocol"
    describe.py            résumé d'une ligne pour le journal
  trace/                   trace TX / RX et replay
    events.py              TraceEvent
    recorder.py            enregistrement au fil de l'eau
    files.py               lecture / écriture d'un fichier de trace
    analysis.py            échanges, statistiques de temps, délais du replay
    compare.py             comparaison des réponses, timeout
    document.py            trace ouverte dans le panneau Replay : modification, renommage
ui/                        interface Tkinter
  app/                     fenêtre principale (une classe App en plusieurs parties)
    window.py              création des panneaux et placement, bouton « Couleurs… »
    messages.py            messages de l'onglet Manuel
    sending.py             envois, séquences, lecture du port série
    protocol.py            protocole en cours, bibliothèque, timeout de réponse
    traces.py              trace, panneau Replay, flèches « → Replay »
    layout.py              séparateurs, panneau Replay affiché / masqué, fermeture
  protocol/                onglet Protocole
    panel.py               ProtocolPanel : création, choix du protocole
    query.py               partie Requête (TX)
    command_search.py      CMD TX : recherche en tapant, propositions, favoris
    response.py            partie Réponse (RX) et résumés du moniteur
    widgets.py             FieldTable (tableau d'une trame, modifiable sur place)
    from_replay.py         ligne du Replay chargée dans la Requête ou la Réponse
    highlight.py           cadre rempli depuis le Replay sur fond gris foncé
    constants.py           libellés et couleurs
  replay/                  panneau Replay (à droite des onglets)
    panel.py               ReplayPanel : relie les éléments ci-dessous
    file_bar.py            ouvrir, nommer / renommer, enregistrer
    options.py             rythme, timeout, comparer
    edit_bar.py            ajouter, supprimer, déplacer ; choix de la flèche
    table.py               tableau modifiable
    detail.py              ligne sélectionnée : intervalle, couleurs, décodage
    player.py              moteur du replay (envois, réceptions, verdicts)
    constants.py           couleurs, icônes, colonnes
  com_panel.py             panneau « Liaison » : série ou TCP
  i18n.py                  langue de l'interface : _() et tr()
  icon.py                  icône de la fenêtre (assets/icon.png)
  lang/en.json             traductions anglaises (textes et modèles de messages)
  messages_panel.py        liste des messages (onglet Manuel)
  save_dialog.py           fenêtre « Sauvegarder le message » (nom, fichier Msg_ proposé)
  tooltip.py               infobulles
  params_panel.py          paramètres du message, aperçu, envoi (onglet Manuel)
  hexview.py               trames hexa en couleurs
  theme.py                 couleurs de l'interface (réglables, mémorisées), abonnements
  color_dialog.py          page « Couleurs… » : échantillon, hexa, palette, aperçu
  monitor_panel.py         journal TX/RX, hexa libre
edition.json               version du logiciel : nom, titre, icône, protocole par défaut (core/edition.py)
assets/icon.png            icône de la fenêtre (PNG, remplaçable)
protocols/                 structure des trames, un fichier par protocole (CONF_PROTOCOLE.md)
  LISEZMOI_CONF.txt        toutes les clés et valeurs possibles, avec exemples (README_CONF.txt : anglais)
  *.json                   protocoles fournis avec la version (liste dans le README)
msgLibrary/
  msgManual/               messages seuls de l'onglet Manuel (Msg_*.json, clé "messages")
  msgList/                 listes de commandes des protocoles (Msg_*.json, clé "commands" ; sous-dossiers par protocole)
tools/
  hexterm.py               terminal hexa en ligne de commande
  gen_test_vectors.py      génère tests/vectors.json
  gen_protocol_vectors.py  génère tests/protocol_vectors.json
tests/
  vectors.json             trames de référence, partagées avec js/
  protocol_vectors.json    résultats de référence du moteur de protocole, partagés avec js/
  test_vectors.py          vérifie core/frames.py contre les vecteurs
  test_protocol.py         tests du moteur de protocole et des fichiers de protocols/
  test_protocol_vectors.py vérifie core/protocol contre les vecteurs
  test_commands.py         tests de la bibliothèque de commandes
  test_trace.py            tests de la trace, du replay et de TraceDocument
  test_links.py            découpage des trames, JSON avec commentaires, liaison TCP
  test_i18n.py             traductions (tous les textes de ui/ traduits, modèles de messages)
  test_request_message.py  messages de protocole, sauvegarde, doublons
  test_ports.py            filtre des ports (VID / PID, Bluetooth)
  data/                    données d'essai communes (protocole, messages, commandes d'un appareil fictif)
js/                        paquet TypeScript (voir INTERFACE.md)
  src/core/                frames, messages, framer, jsonc (JSON avec commentaires)
  src/core/protocol/       moteur de protocole : même découpage que core/protocol/
  src/link/                SerialLink et interface SerialTransport
  src/electron/            process principal (serialport) et preload
  src/react/               hooks React
  examples/                écran React complet, extraits main / preload
  test/                    tests vitest, dont les vecteurs partagés
docs/Francais/             documentation en français
docs/English/              documentation en anglais
Claude_IA/                 consignes pour Claude (CLAUDE.md) et état du projet (STATUS.md)
```

`core/` (Python) et `js/src/core/` (TypeScript) implémentent le même format de messages et le même moteur de protocole ; `tests/vectors.json` et `tests/protocol_vectors.json` garantissent qu'ils produisent les mêmes octets (et les mêmes messages d'erreur). Après une modification de `core/frames.py` ou `core/protocol/`, relancer `python tools/gen_test_vectors.py` / `python tools/gen_protocol_vectors.py` puis les tests des deux côtés.

## Principe

Le code est séparé en deux couches :

- **`core/`** contient toute la logique : construire une trame, lire les fichiers de messages, piloter le port série. Il ne dépend pas de Tkinter et peut être réutilisé dans un script ou des tests.
- **`ui/`** contient l'interface. Chaque panneau est indépendant et reçoit des fonctions de rappel (callbacks). Seul `ui/app/` connaît tous les panneaux et les relie entre eux.

Règles d'écriture :
- un fichier par sujet, des fonctions courtes avec un nom qui dit ce qu'elles font, des commentaires en français ;
- les gros panneaux sont des **paquets** (`ui/protocol/`, `ui/replay/`, `ui/app/`) : une classe principale assemblée à partir de parties (« mixins ») ou de petits widgets, un fichier chacun ;
- les choix entre plusieurs cas s'écrivent en `if / elif / else` : SerialHex se développe en Python 3.9 (minimum du débogueur VS Code) et reste compatible **Python 3.8** ; ni l'un ni l'autre n'a le `match / case` (Python 3.10). Côté TypeScript, `switch / case` ;
- les règles qui ne dépendent pas de l'affichage (validation, renommage, calculs) vont dans `core/`, où elles sont testées sans interface.

```
            ┌──────────────────── ui/app/ ─────────────────────┐
            │  ComPanel                                        │
            │  onglets : Manuel (MessagesPanel + ParamsPanel), │
            │            Protocole (ui/protocol/)              │
            │  panneau Replay (ui/replay/)                     │
            │  MonitorPanel                                    │
            └────┬───────────┬───────────┬──────────┬──────────┘
                 │           │           │          │
       core/serial_link  core/messages  core/protocol  core/commands, core/trace
                   │                             
               pyserial                          
```

## Modules `core/`

### `frames.py`
Fonctions pures, sans état.

| Fonction | Rôle |
|---|---|
| `build_frame(msg, values)` | Assemble la trame d'un message à partir des valeurs de ses paramètres |
| `encode_param(name, pdef, value)` | Encode une valeur selon son type (`u8`, `u16be`, `enum`…) |
| `checksum(algo, data)` | Calcule un checksum (`xor8`, `sum8`, `crc16_modbus`…) |
| `defaults_for(msg)` | Valeurs par défaut des paramètres d'un message |
| `parse_hex`, `to_hex`, `to_ascii` | Conversions texte ↔ octets |

### `messages.py`

| Fonction | Rôle |
|---|---|
| `load_messages(path)` | Charge et valide un fichier ; le groupe vient du nom du fichier |
| `load_folder(folder)` | Charge tous les `Msg_*.json`, retourne `(messages, erreurs)` |
| `merge_messages(messages, new)` | Ajoute des messages sans doublon (identiques ignorés ; même nom, contenu différent : `"display"` complété par le fichier d'origine) |
| `merge_files(folder, out)` | Fusionne tous les fichiers en un seul |

### `request_message.py`

Messages « de protocole » (clé `"request"`) : `build_request(msg, values, protocol, kind)` construit la trame avec le protocole en cours ; `make_request_message`, `save_message_file`, `find_saved`, `unique_name`, `file_name_for` servent au bouton « Sauvegarder… » de l'onglet Protocole.

### `protocol/`

Moteur de protocole requête / réponse : la structure des trames vient d'un fichier de `protocols/` (détails : [PROTOCOLE.md](PROTOCOLE.md)).

| Élément | Rôle |
|---|---|
| `load_protocol(path)` / `list_protocols(dossier)` | Lit et valide un fichier de protocole (`ProtocolError` avec un message lisible) |
| `Protocol` | Un protocole : `build(kind, data, values)`, `build_query`, `build_response`, `decode(frame, kind)`, `matches(frame, kind)`, `crc_bytes`, `spec` / `has` / `max_value` ; expose `byte_order` (passé à `core.commands`) |
| `Decoded` | Trame décodée : `fields`, `errors`, `complete`, `extra`, `ok`, et par rôle `request_id`, `command_id`, `error`, `length`, `data`, `crc_ok` |
| `Crc`, `CRC_PRESETS` | CRC 8 / 16 / 32 (modèle width / poly / init / refin / refout / xorout) et sommes |
| `color_segments(decoded)` | Couleurs des champs (fichier de conf), utilisées par `ui/hexview.py` |
| `DEFAULT_PROTOCOL`, `build_query`, `decode`… | Protocole générique intégré et fonctions raccourcies (scripts, tests) |

### `commands/`

Bibliothèque des commandes du protocole, lue dans les clés `"commands"` et `"errors"` des `Msg_*.json`.

| Élément | Rôle |
|---|---|
| `load_library(folder, protocol_name)` | Commandes + codes d'erreur de tous les fichiers ; `Library.problems` liste les définitions invalides, `Library.skipped` les fichiers écrits pour un autre protocole (clé `"protocol"`) |
| `Library.by_id(id)` / `error_text(code)` | Commande d'après son COMMAND ID / texte d'un code d'erreur |
| `encode_field(s)(...)` | Valeurs physiques → octets (facteur, offset, bornes, ordre des octets) |
| `decode_fields(defs, data, cfg)` | Octets → champs avec valeur physique, unité, contrôle de plage |
| `describe(decoded, cmd, lib)` | Résumé d'une ligne avec nom de commande et texte d'erreur |

### `trace/`

| Élément | Rôle |
|---|---|
| `TraceRecorder` | Enregistre chaque trame TX / RX au fil de l'eau (CSV) |
| `load_trace` / `save_trace` | Lecture / écriture d'un fichier complet |
| `exchanges`, `analyze`, `replay_delays` | Échanges, statistiques de temps, délais du replay |
| `compare`, `judge_exchange` | Octets en cause, verdict avec timeout |
| `TraceDocument` | Trace ouverte dans le panneau Replay : `set_cell` (validation), `insert_after` (temps au milieu de l'intervalle, ou « Délai fixe » après la ligne du dessus avec décalage des suivantes), `replace`, `move`, `delete`, `gaps`, `save_as_name` (renommage, `FileExistsError` si le nom est pris) |

### `serial_link.py`

| Élément | Rôle |
|---|---|
| `list_serial_ports(usb_ids, hide_bluetooth)` | Ports présents, triés (COM3 avant COM10), filtrés par VID / PID (`core/port_filter.py`), Bluetooth masqué |
| `check_port(device)` | Teste l'ouverture : `libre`, `occupé`, `absent` ou `erreur` |
| `SerialLink.connect(...)` | Ouvre le port ; lève `ConnectionError` avec un message lisible |
| `SerialLink.reconfigure(...)` | Change vitesse / format sans fermer le port |
| `SerialLink.write(data)` | Envoie des octets, compte les octets TX |
| `SerialLink.set_lines(dtr, rts)` | Pilote les lignes DTR / RTS |
| `SerialLink.events` | File d'événements : `("rx", bytes)` ou `("lost", message)` |

La lecture tourne dans un **thread** dédié. Les octets reçus sont regroupés en une trame tant que le silence entre deux octets reste inférieur à `gap_ms`, ou jusqu'au délimiteur `frame_end` s'il est réglé (Modbus ASCII) : voir `framing.py`. Les événements sont déposés dans une `queue.Queue` ; l'interface les dépile toutes les 30 ms depuis son propre thread, car Tkinter n'accepte pas d'être appelé depuis un autre thread.

À l'ouverture, DTR et RTS sont laissés inactifs pour ne pas redémarrer une carte Arduino / ESP32. Sous Linux et macOS, le port est ouvert en mode exclusif pour détecter qu'il est déjà utilisé ; sous Windows c'est le comportement par défaut.

### `tcp_link.py`, `link_switch.py`

`TcpLink` a la même interface que `SerialLink` (`connect(host, port)`, `write`, `events`, `gap_ms`, `frame_end`) ; `reconfigure` et `set_lines` sont sans effet. `LinkSwitch` contient les deux liaisons et transmet tout à la liaison active (`mode` = `"serial"` ou `"tcp"`, réglage `link`) : l'application et le panneau Liaison ne voient qu'un seul objet.

### `jsonc.py`

`load_file(path)` / `loads(text)` : JSON avec commentaires `//` et `/* */`, remplacés par des espaces avant la lecture (les numéros de ligne des erreurs restent justes). Utilisé pour les fichiers de protocole et les `Msg_*.json` ; même fonction en TypeScript (`parseJsonc`).

### Langue de l'interface (`ui/i18n.py`)

Le code est écrit en français ; chaque texte affiché passe par `_()` (`_("Envoyer")`, `_("Connecté : {0}").format(...)`), traduit d'après `ui/lang/en.json`. Les messages construits par `core/` (décodage, erreurs de liaison, chargement des fichiers) passent par `tr()`, qui les traduit d'après des modèles (expressions régulières) du même fichier. La langue est choisie au démarrage par `serialhex.py`, avant l'import des panneaux ; changer de langue relance le programme. `tests/test_i18n.py` vérifie que tous les textes de `ui/` ont une traduction.

### `settings.py`
`Settings` est un dictionnaire sauvegardé dans `settings.json` : dernier port, vitesse, format, délai de fin de trame, connexion auto, protocole choisi, couleurs, langue, fichiers de messages ajoutés (`message_files`), taille de la fenêtre et position des séparateurs.

## Modules `ui/`

| Fichier | Classe | Reçoit | Rôle |
|---|---|---|---|
| `app/` | `App` | — | Crée les panneaux, détient la liste des messages et les valeurs des paramètres, fait les envois, dépile les événements série, affiche / masque le panneau Replay |
| `com_panel.py` | `ComPanel` | `link`, `settings`, `log`, `on_change` | Choix du port, réglages, connexion, surveillance des ports |
| `messages_panel.py` | `MessagesPanel` | `on_select`, `on_send`, `on_send_selection`, `on_reload`, `on_load_files`, `on_remove` | Arbre des messages par groupe |
| `params_panel.py` | `ParamsPanel` | `on_send`, `on_to_replay`, `build` | Formulaire, aperçu de la trame, envoi périodique, flèche « → Replay » (onglet Manuel, à droite des messages) |
| `protocol/` | `ProtocolPanel` | `settings`, `on_send`, `on_protocol`, `on_to_replay`, `on_save` | Onglet Protocole : choix du protocole, requête depuis la bibliothèque, décodage des réponses (type auto / manuel). Reçoit le protocole par `set_protocol`, la bibliothèque par `set_library`, chaque envoi par `on_sent`, chaque réception par `on_received` |
| `replay/` | `ReplayPanel` | `send`, `is_connected`, `traces_dir`, `log`, `describe`, `style`, `on_decode` | Panneau Replay : trace modifiable, renommage, détail de ligne, replay avec comparaison. Reçoit chaque réception par `on_received`, les trames des flèches par `put_frame` |
| `monitor_panel.py` | `MonitorPanel` | `on_gap_change`, `on_send_hex`, `crc_bytes`, `annotate` | Journal horodaté, décodage protocole, hexa libre avec CRC du protocole |

## Ajouter une fonctionnalité

- **Un nouveau type de paramètre** : `encode_param` dans `core/frames.py`, et le widget correspondant dans `ParamsPanel._add_field`.
- **Un nouveau checksum** : `checksum` dans `core/frames.py` (messages libres) ; pour le protocole, un CRC se décrit dans le fichier de `protocols/` sans toucher au code.
- **Un nouveau protocole** : copier `protocols/exemple_generique.json`, décrire les champs ; il apparaît dans la liste de l'onglet Protocole.
- **Un nouveau panneau** : créer `ui/mon_panel.py` (ou un paquet `ui/mon_panel/`) avec ses callbacks, puis l'instancier et le placer dans `App._build` (`ui/app/window.py`).
