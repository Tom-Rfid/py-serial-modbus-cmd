# S'interfacer avec SerialHex

[← Retour au README](../../README.md)

Ce document s'adresse à ceux qui **maintiennent SerialHex** ou qui veulent **brancher une autre application** dessus (par exemple une interface Electron / React). Il décrit ce que SerialHex expose et ce qui doit rester stable.

Un guide pratique côté application React peut être placé dans le dépôt de l'application qui utilise le paquet (`docs/SERIALHEX.md`).

| Dépôt | Contenu |
|---|---|
| `GUI_PyCommSerial` | Ce projet : outil Python SerialHex + paquet npm `serialhex` (`js/`) |
| application cliente | Application Electron / React qui utilise le paquet `serialhex` |

## Principe

Une application React **n'appelle pas Python à l'exécution**. SerialHex existe en deux implémentations qui partagent un même contrat :

```
                        ┌───────────── le contrat ─────────────┐
                        │  Msg_*.json   (format)           │
                        │  tests/vectors.json (trames attendues)│
                        └──────────────┬───────────────────────┘
                 ┌─────────────────────┴─────────────────────┐
      Python : serialhex.py + core/              TypeScript : js/ (paquet npm « serialhex »)
      outil autonome, open source                intégré dans l'application Electron / React
```

- Les **mêmes fichiers de messages** fonctionnent dans les deux.
- Les **mêmes trames** sont produites, garanti par `tests/vectors.json`.
- L'application installe le paquet `js/` ; elle n'a besoin ni de Python ni de l'interface Tkinter.

Cela évite d'embarquer un interpréteur Python dans l'installeur et un process supplémentaire à surveiller.

## Les quatre points d'interface

### 1. Le format des messages

Défini dans [MESSAGES.md](MESSAGES.md). C'est l'interface principale : un client ou une application ne voit que ces fichiers.

Points stables :
- nom des fichiers `Msg_<fonction>.json`, groupe déduit du nom ;
- clés `name`, `frame` (ou `request`, message de protocole), `params`, `checksum`, `description`, `group` ;
- types de paramètres et algorithmes de checksum existants : leur encodage ne change jamais.

### 2. Les vecteurs de test

`tests/vectors.json` liste, pour chaque cas, un message, des valeurs et la trame attendue (ou une erreur attendue). `tests/protocol_vectors.json` fait de même pour le moteur de protocole : trames construites, trames décodées (champs, contrôles, messages d'erreur, couleurs), valeurs de contrôle des CRC, fichiers de protocole invalides. Ils sont **générés par Python** et **vérifiés par les deux implémentations**.

```bash
python tools/gen_test_vectors.py     # régénère tests/vectors.json
python tools/gen_protocol_vectors.py # régénère tests/protocol_vectors.json
python -m unittest discover tests    # vérifie Python
cd js && npm test                    # vérifie TypeScript
```

### 3. L'API du paquet TypeScript

| Import | Exporte |
|---|---|
| `serialhex` | `buildFrame`, `defaultsFor`, `toHex`, `toAscii`, `parseHex`, `parseMessageFile`, `loadMessageFiles`, `groupMessages`, `FrameAssembler`, `SerialLink`, `getSerialHexBridge`, types ; protocole : `parseProtocol`, `Protocol`, `Decoded`, `QUERY`, `RESPONSE`, `CRC_PRESETS`, `Crc`, `DEFAULT_PROTOCOL`, `protocolSegments`, `ProtocolError`, `AsciiHex`, `valueText` ; `parseJsonc` (JSON avec commentaires) |
| `serialhex/react` | `useLinkState`, `useSerialPorts`, `usePortCheck`, `useLinkLog`, `useMessages`, `useMessageForm`, `usePeriodic`, `messageKey` |
| `serialhex/electron/main` | `registerSerialHexIpc`, `listPorts`, `checkPort`, `openPort`, `readMessageFiles`, `readProtocolFiles` |
| `serialhex/electron/preload` | `exposeSerialHex`, `createSerialHexBridge` |

Correspondance avec Python :

| Python | TypeScript |
|---|---|
| `core/frames.py` → `build_frame`, `defaults_for`, `checksum` | `buildFrame`, `defaultsFor`, `checksum` |
| `core/messages.py` → `load_messages`, `load_folder` | `parseMessageFile`, `loadMessageFiles` |
| `core/protocol/` → `load_protocol`, `Protocol.build` / `decode` / `matches` / `crc_bytes`, `color_segments` | `parseProtocol`, `Protocol.build` / `decode` / `matches` / `crcBytes`, `protocolSegments` |
| `Decoded.request_id`, `command_id`, `error`, `data`, `crc_ok` | `Decoded.requestId`, `commandId`, `error`, `data`, `crcOk` |
| `core/serial_link.py` → `SerialLink`, `check_port`, `list_serial_ports` | `SerialLink`, `checkPort`, `listPorts` |
| états `libre` / `occupé` / `absent` / `erreur` | `free` / `busy` / `missing` / `error` |
| `ui/*` (Tkinter) | `serialhex/react` (hooks, sans rendu imposé) |

### 4. Le protocole IPC Electron

Utile si l'application veut écrire son propre preload ou appeler les canaux directement. Tous les appels passent par `ipcRenderer.invoke` et répondent :

```ts
{ ok: true, value: ... }  |  { ok: false, error: "message lisible en français" }
```

| Canal | Arguments | Réponse |
|---|---|---|
| `serialhex:list` | — | `PortInfo[]` (`path`, `description`, `manufacturer`, `vendorId`, `productId`, `serialNumber`) |
| `serialhex:check` | `path` | `{ status: 'free' \| 'busy' \| 'missing' \| 'error', message }` |
| `serialhex:open` | `{ path, baudRate, dataBits?, parity?, stopBits?, flow? }` | — |
| `serialhex:reconfigure` | `{ baudRate?, dataBits?, parity?, stopBits?, flow? }` | — |
| `serialhex:close` | — | — |
| `serialhex:write` | `Uint8Array` | — (résolu une fois les octets transmis) |
| `serialhex:signals` | `{ dtr?, rts? }` | — |
| `serialhex:read-messages` | — | `[{ fileName, content }]` du dossier `messagesDir` |
| `serialhex:read-protocols` | — | `[{ fileName, content }]` des `*.json` du dossier `protocolsDir` |

Événements envoyés par le process principal à la fenêtre qui a ouvert le port :

| Canal | Charge |
|---|---|
| `serialhex:data` | `Uint8Array`, octets bruts reçus (le découpage en trames est fait côté renderer) |
| `serialhex:closed` | `string`, raison d'une fermeture **non demandée** (câble retiré, erreur) |

Comportement du process principal :
- un seul port ouvert à la fois ; ouvrir un nouveau port ferme le précédent ;
- le port est fermé si la fenêtre qui l'a ouvert est détruite ;
- le renderer ne peut lire que les dossiers `messagesDir` et `protocolsDir` passés à `registerSerialHexIpc`.

## Protocole requête / réponse

Le **moteur de protocole** existe dans les deux langages : `core/protocol/` et `js/src/core/protocol/` (même découpage en fichiers) lisent le même fichier de `protocols/` (toutes les options : [CONF_PROTOCOLE.md](CONF_PROTOCOLE.md)) et donnent les mêmes résultats, vérifiés par `tests/protocol_vectors.json`.

```ts
// process principal : registerSerialHexIpc(ipcMain, { messagesDir, protocolsDir })
import { parseProtocol, QUERY, RESPONSE, protocolSegments } from 'serialhex';

const files = await window.serialhex.readProtocolFiles();          // [{ fileName, content }]
const modbus = files.find((f) => f.fileName === 'modbus_rtu.json')!;
const proto = parseProtocol(modbus.content, modbus.fileName);          // ProtocolError si invalide

const frame = proto.buildQuery(1, 0x03, Uint8Array.of(0, 0, 0, 2));  // Modbus : lire 2 registres
await link.send(frame);

const d = proto.decode(rx, RESPONSE);
if (d.ok && d.error === 0) console.log(d.requestId, d.data?.raw);
const colors = protocolSegments(d);                                  // [début, longueur, 'hdr' | 'cmd' | 'crc' | 'err' | 'perr_ok' | 'perr_ko']
```

Formats à plusieurs trames, codage ASCII et textes (mêmes clés que le fichier Python) :

```ts
const mbus = parseProtocol(text, 'mbus.json');                       // commentaires // et /* */ acceptés
mbus.variantNames(QUERY);                                            // ['Courte', 'Longue']
mbus.build(QUERY, new Uint8Array(), { request_id: 5, command_id: 0x5B }, 'Courte');   // 10 5B 05 60 16
const r = mbus.decode(rx, RESPONSE);                                 // r.variant : 'Accusé' | 'Longue'
r.fields.map((f) => [f.name, f.meaning, f.description]);             // "values" / "description" du fichier
mbus.language = 'en';                                                // textes {"fr", "en"} en anglais
mbus.errorTexts();                                                   // {code: texte} dans la langue choisie

const ascii = parseProtocol(text2, 'modbus_ascii.json');             // "encoding": ascii_hex
ascii.frameEnd;                                                      // Uint8Array [0x0D, 0x0A] : découpe des trames reçues
const dd = ascii.decode(rx2, RESPONSE);                              // dd.binary = trame binaire, dd.encoded = octets reçus
ascii.displaySegments(dd, protocolSegments(dd));                     // couleurs des caractères ASCII
```

La **bibliothèque de commandes** (`core/commands/` : champs `tx` / `rx`, unités, facteur / offset, choix, bits) n'existe encore qu'en Python. Les fichiers `Msg_*.json` qui contiennent des `"commands"` ou des `"errors"` sont acceptés par le paquet TypeScript (ignorés, sans erreur). Prochaine étape pour le GUI React : la porter dans `js/src/core/commands.ts`, sur le même principe de vecteurs partagés.

### Faire évoluer le moteur de protocole

1. Python : `core/protocol/` ; TypeScript : `js/src/core/protocol/` (mêmes fichiers, mêmes règles, mêmes messages d'erreur).
2. Ajouter des structures d'essai dans `tools/gen_protocol_vectors.py`, puis `python tools/gen_protocol_vectors.py`.
3. Lancer les tests des deux côtés.

## Faire évoluer SerialHex

### Ajouter un type de paramètre ou un checksum

1. Python : `encode_param` ou `checksum` dans `core/frames.py`, widget dans `ui/params_panel.py`.
2. TypeScript : `encodeParam` ou `checksum` dans `js/src/core/frames.ts`, type dans `js/src/core/types.ts`.
3. Ajouter des cas dans `tools/gen_test_vectors.py`, puis régénérer `tests/vectors.json`.
4. Lancer les tests des deux côtés.
5. Documenter dans [MESSAGES.md](MESSAGES.md).

### Ce qui ne doit jamais changer

- L'encodage d'un type ou d'un checksum existant : des fichiers de messages livrés à des clients en dépendent.
- Le nom et le sens des clés du JSON.
- Les noms des canaux IPC et la forme `{ ok, value | error }`.

Pour un changement incompatible, créer un nouveau type ou un nouvel algorithme plutôt que modifier l'existant.

### Versions du paquet

`js/package.json` suit le versionnage sémantique :

| Changement | Version |
|---|---|
| Correction sans effet sur l'API | `0.1.0` → `0.1.1` |
| Nouveau type, checksum, hook, fonction | `0.1.0` → `0.2.0` |
| API modifiée ou supprimée | `0.x` → `1.0.0` (puis majeure suivante) |

Noter chaque version dans les notes de version du dépôt, pour que l'application sache si elle peut mettre à jour sans risque.

## Distribuer le paquet

| Méthode | Commande côté SerialHex | Côté application |
|---|---|---|
| Dossier local | `cd js && npm install && npm run build` | `npm install ../GUI_PyCommSerial/js` |
| Sous-module Git | — | `git submodule add <url-GUI_PyCommSerial> GUI_PyCommSerial` puis `npm install ./GUI_PyCommSerial/js` |
| Archive | `cd js && npm pack` | `npm install ./serialhex-0.1.0.tgz` |
| Registre npm | `cd js && npm publish` | `npm install serialhex` |

## Messages publics et messages propriétaires

Le dépôt `GUI_PyCommSerial` est open source : `msgLibrary/` ne contient que des exemples ou les commandes destinées aux clients. Les fichiers de messages propres à une application (commandes internes d'un produit) restent dans le dépôt privé de cette application. Le format étant identique, on peut livrer un fichier précis à un client sans exposer le reste.
