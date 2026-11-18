# Fichier de protocole : toutes les options

[← Retour au README](../../README.md) · [Protocole et onglet Protocole](PROTOCOLE.md)

SerialHex est un logiciel **standard** : la structure des trames d'un appareil est décrite dans un **fichier de protocole** (dossier `protocols/`), sans toucher au code. Ce document liste **toutes** les clés possibles, avec leur rôle et des exemples.

- Le fichier est en JSON (UTF-8). Les nombres s'écrivent en décimal (`83`) ou en texte hexa / binaire (`"0x7E"`, `"0b0101"`).
- **Commentaires** acceptés, comme dans VS Code : `// jusqu'à la fin de la ligne` et `/* sur plusieurs lignes */` (un `//` dans une chaîne, comme `"http://…"`, n'est pas un commentaire). VS Code ouvre `protocols/*.json` en « JSON with Comments ».
- **Une clé à `null` est ignorée** : on peut garder toutes les clés dans un champ, remplies si elles servent, à `null` sinon : `{"name": "SYNC", "size": 1, "role": "value", "value": "0x7E", "LENb": null, "at": null, "if": null}`.
- Un fichier invalide est signalé dans le moniteur avec la raison exacte, et SerialHex utilise le protocole générique intégré à la place.
- Le même fichier est lu par l'outil Python et par le paquet TypeScript du GUI React (`parseProtocol`).
- Résumé de toutes les clés et valeurs possibles, en texte simple : `protocols/LISEZMOI_CONF.txt` (en anglais : `protocols/README_CONF.txt`).

**Fichiers fournis avec la version Techmelec** (tous commentés en français et en anglais) :

| Fichier | Protocole | Particularités montrées |
|---|---|---|
| `modbus_rtu.json` | Modbus RTU | CRC poids faible en premier, réponse normale / exception (variantes + bits) |
| `modbus_ascii.json` | Modbus ASCII | codage `ascii_hex` (`:` … CR LF), LRC |
| `modbus_tcp.json` | Modbus TCP | en-tête MBAP, longueur, liaison TCP |
| `mbus.json` | M-Bus | 3 formats (E5 / court / long), longueur répétée (`copy`), somme sur 8 bits, little endian |
| `profibus_fdl.json` | PROFIBUS FDL | SD1 / SD2 / SD3 / SD4 / E5, adresses avec bit d'extension (`LENb`) |
| `exemple_generique.json` | modèle | SYNC AA 55, numéro 16 bits, CRC16 CCITT |

Fonctions Modbus standard pour tout appareil : `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json`. Exemples de commandes pour des appareils **fictifs** : `msgLibrary/msgList/modbus/`, `msgLibrary/msgList/mbus/`, `msgLibrary/msgList/profibus/`.

## Sommaire

1. [Clés du fichier](#1-clés-du-fichier)
2. [Clés d'un champ](#2-clés-dun-champ)
3. [Rôles](#3-rôles)
4. [CRC et sommes](#4-crc-et-sommes)
5. [Plage d'un CRC : `over`](#5-plage-dun-crc--over)
6. [Taille des données](#6-taille-des-données)
7. [Conditions : `if`](#7-conditions--if)
8. [Placement des champs : `at` et `after`](#8-placement-des-champs--at-et-after)
   - [8 bis. Champs en bits : `LENb`, `atb`, `bit_order`](#8-bis-champs-en-bits--lenb-atb-bit_order)
   - [8 ter. Plusieurs formats de trame : `variants`](#8-ter-plusieurs-formats-de-trame--variants)
   - [8 quater. Codage sur la ligne : `encoding`](#8-quater-codage-sur-la-ligne--encoding)
9. [Couleurs](#9-couleurs)
   - [9 bis. Textes lisibles : descriptions, valeurs, catégories](#9-bis-textes-lisibles--descriptions-valeurs-catégories)
10. [Exemples complets](#10-exemples-complets)
11. [Messages d'erreur au chargement](#11-messages-derreur-au-chargement)
12. [Lien avec les fichiers de commandes](#12-lien-avec-les-fichiers-de-commandes)

## 1. Clés du fichier

| Clé | Obligatoire | Valeurs | Rôle |
|---|---|---|---|
| `name` | non (nom du fichier par défaut) | texte | Nom affiché dans la liste de l'onglet Protocole ; les fichiers `Msg_*.json` y font référence (clé `protocol`) |
| `description` / `description_en` | non | texte | Affichée à côté de la liste (en anglais si l'interface est en anglais) |
| `byte_order` | non (`little`) | `little`, `big` | Ordre des octets de tous les champs et CRC de plus d'un octet. `little` : poids faible en premier (`0x1234` → `34 12`) ; `big` : poids fort en premier (`0x1234` → `12 34`, registres Modbus, ordre réseau) |
| `encoding` | non (`binary`) | `"binary"`, `{"type": "ascii_hex", …}` | Codage de la trame sur la ligne (§8 quater) |
| `bit_order` | non (`msb`) | `msb`, `lsb` | Numérotation des bits pour les champs en bits (§8 bis) : `msb` = bit 0 = poids fort de l'octet 0 |
| `crc` | non | objet `{nom: définition}` | CRC utilisés par les champs, chacun nommé (voir §4) |
| `tx` | **oui** | liste de champs, ou `{"variants": […]}` | Trame de **requête** (envoyée à l'appareil), champs dans l'ordre des octets ; plusieurs formats possibles (§8 ter) |
| `rx` | **oui** | liste de champs, ou `{"variants": […]}` | Trame de **réponse** (reçue de l'appareil) |
| `commands` | non | chemin | Dossier des commandes `Msg_*.json`, **relatif au fichier de protocole** (`"../messages"`). Absent : pas de bibliothèque de commandes |
| `errors` | non | objet `{code: texte}` ou `{code: {"fr": …, "en": …}}` | Textes des codes d'erreur (rôle `error`). Prioritaires sur ceux des `Msg_*.json` |
| `categories` | non | objet `{code: texte}` ou `{code: {"fr": …, "en": …}}` | Catégories des commandes (clé `group` des `Msg_*.json`, ex. `LAS`, `COM`) : texte affiché avec la description de la commande (§9 bis) |
| `_comment` | non | texte | Commentaire libre (ignoré) |

## 2. Clés d'un champ

| Clé | Pour quels rôles | Valeurs | Rôle |
|---|---|---|---|
| `name` | tous, **obligatoire** | texte, unique dans `tx` (ou `rx`) | Nom affiché dans les tableaux ; sert de référence dans `over`, `of` et `if` |
| `role` | tous | voir §3 (majuscules acceptées : `"NA"`) | Ce que représente le champ. Par défaut `value` si `value` est donné, sinon `field` |
| `size` ou `LENO` | tous (facultatif pour `data` et `crc`) | `value`, `request_id`, `command_id`, `length`, `error`, `field` : **0 à 4** ; `na` : 0 à 255 ; `data` : 0 à 65535 | Taille en **octets**. **`0` = champ absent** (on peut le laisser dans le fichier pour mémoire). CRC : taille de l'algorithme par défaut |
| `LENb` | tous sauf `data` et `crc` | 0 à 32 bits (`na` : 0 à 2040) | Taille en **bits** : `"LENO": 1` = `"LENb": 8` (§8 bis). Une seule taille par champ |
| `value` | `value` | entier qui tient dans `size` | Valeur attendue (vérifiée au décodage, écrite à la construction) |
| `default` | `field` | entier | Valeur écrite à la construction si rien n'est fourni (`0` par défaut) |
| `fill` | `na` | 0 à 255 | Octet écrit à la construction dans les octets non lus (`0` par défaut) |
| `of` | `length` | nom, ou liste de noms | Champ(s) dont la longueur est comptée |
| `algo` | `crc` | nom de la section `crc`, ou nom prêt à l'emploi (§4) | Algorithme du CRC |
| `over` | `crc` | `[début, fin]` (§5) | Octets couverts par le CRC. Défaut : du début de la trame jusqu'au CRC |
| `if` | tous | nom d'un champ | Le champ n'existe que si le champ nommé est présent et non vide / non nul (§7) |
| `order` | tous les champs numériques et CRC | `little`, `big` | Ordre des octets propre à ce champ (remplace `byte_order`) |
| `color` | tous | `hdr`, `cmd`, `crc`, `na`, ou `"#RRGGBB"` | Couleur à l'affichage (§9) |
| `at` ou `atO` | tous | numéro d'octet, `"start"`, `"end"` | Placement du champ (§8) |
| `atb` | tous | numéro de bit | Placement au bit près : `"atO": 2` = `"atb": 16` (§8 bis) |
| `after` | tous | nom d'un champ | Placé juste après ce champ (§8) |
| `same_as` | `copy` | nom d'un champ précédent | Champ recopié (longueur répétée M-Bus / PROFIBUS) |
| `description` / `description_en` | tous | texte | Texte libre, affiché dans la colonne Description des tableaux (§9 bis) |
| `values` | tous les champs numériques | `{valeur: texte}` ou `{valeur: {"fr": …, "en": …}}` | Sens de chaque valeur, affiché à côté de la valeur décodée : `3 (0x03) Lecture de registres` (§9 bis) |
| `category` | tous | texte | Étiquette libre (classement, filtres d'outils externes) |

## 3. Rôles

| Rôle | Au plus un par sens | Construction (envoi) | Décodage (réception) |
|---|---|---|---|
| `value` | non | écrit `value` | vérifie la valeur ; sinon erreur `SYNC différent de 0xA55A` et octets en rouge. Les octets fixes du **début** servent aussi à reconnaître les trames du protocole dans le moniteur |
| `request_id` | oui | valeur fournie (champ REQUEST ID de l'onglet, affiché en hexa : `0x05`) ; la case « REQ+ » (auto req_id) repart à 0 après le maximum (0xFF sur 1 octet, 0xFFFF sur 2) | relie la réponse à sa requête : type de réponse « Auto », timeout de réponse, résumés `réponse #0x05` |
| `command_id` | oui | valeur fournie (COMMAND ID de la commande choisie) | choisit la commande de la bibliothèque pour décoder DATA ; si la **réponse** en contient un, il sert directement |
| `length` | oui | calculée : taille des champs de `of` | donne la taille de DATA |
| `error` | oui | valeur fournie (0 par défaut) | fond vert à 0, rouge sinon ; texte d'après `errors` ; une réponse en erreur n'est pas décodée selon la partie `rx` de la commande |
| `crc` | non | calculé en dernier, sur la trame déjà écrite | vérifié ; rouge et `attendu XX XX` s'il est faux |
| `data` | oui | les octets des champs `tx` de la commande (onglet Protocole) | découpés selon les champs `rx` (ou `tx`) de la commande |
| `field` | non | `default`, ou valeur fournie par son nom | lu et affiché, sans contrôle |
| `na` | non | `size` octets valant `fill` | **non lu** : ni valeur ni contrôle, affiché en gris barré, note « non lu ». Les octets restent couverts par les CRC qui les incluent. Plusieurs champs `na` possibles |
| `copy` | non | recopie la valeur déjà écrite du champ `same_as` | vérifie l'égalité ; sinon erreur `L (répété) différent de L` |

**Exemple : octets réservés à ignorer**

```json
{"name": "RÉSERVÉ 1", "size": 2, "role": "na"},
{"name": "RÉSERVÉ 2", "size": 1, "role": "NA", "fill": "0xFF"}
```

## 4. CRC et sommes

Section `crc` : chaque CRC reçoit un nom, utilisé par les champs (`"algo": "modbus"`). Trois écritures :

```json
"crc": {
  "modbus": "crc16_modbus",
  "ccitt":  { "preset": "crc16_ccitt_false" },
  "maison": { "width": 16, "poly": "0x1021", "init": "0xFFFF", "refin": false, "refout": false, "xorout": "0x0000" }
}
```

Un nom prêt à l'emploi peut aussi être mis directement dans `algo` (`"algo": "crc32"`), sans section `crc`.

### Noms prêts à l'emploi

| Nom | width | poly | init | refin | refout | xorout | Valeur pour `123456789` | Usage courant |
|---|---|---|---|---|---|---|---|---|
| `crc16_modbus` | 16 | 0x8005 | 0xFFFF | oui | oui | 0 | 0x4B37 | Modbus RTU |
| `crc16_ccitt_false` | 16 | 0x1021 | 0xFFFF | non | non | 0 | 0x29B1 | nombreux protocoles série |
| `crc16_xmodem` | 16 | 0x1021 | 0x0000 | non | non | 0 | 0x31C3 | XMODEM |
| `crc16_kermit` | 16 | 0x1021 | 0x0000 | oui | oui | 0 | 0x2189 | Kermit, CCITT « true » |
| `crc8` | 8 | 0x07 | 0x00 | non | non | 0 | 0xF4 | SMBus |
| `crc8_maxim` | 8 | 0x31 | 0x00 | oui | oui | 0 | 0xA1 | capteurs 1-Wire (DS18B20) |
| `crc32` | 32 | 0x04C11DB7 | 0xFFFFFFFF | oui | oui | 0xFFFFFFFF | 0xCBF43926 | zip, Ethernet |
| `crc32_mpeg2` | 32 | 0x04C11DB7 | 0xFFFFFFFF | non | non | 0 | 0x0376E6E7 | MPEG-2, STM32 (unité CRC) |
| `sum8` | 8 | — | — | — | — | — | 0xDD | somme des octets, modulo 256 |
| `sum8_2c` | 8 | — | — | — | — | — | 0x23 | complément à 2 : trame + somme = 0 |
| `xor8` | 8 | — | — | — | — | — | 0x31 | XOR de tous les octets (NMEA…) |
| `sum16` | 16 | — | — | — | — | — | 0x01DD | somme des octets, modulo 65536 |

La « valeur pour `123456789` » est la valeur de contrôle des catalogues de CRC (reveng) : elle permet de vérifier un paramétrage avec n'importe quel calculateur en ligne.

### Les paramètres d'un CRC

Un CRC est un registre de `width` bits dans lequel on fait entrer les octets un par un ; à chaque bit, si le bit qui sort vaut 1, on combine le registre avec le polynôme (XOR).

| Paramètre | Signification |
|---|---|
| `width` | Taille du CRC : 8, 16 ou 32 bits (1, 2 ou 4 octets dans la trame) |
| `poly` | Polynôme, en forme **normale** (bit de poids fort implicite). Modbus : `0x8005` |
| `init` | Valeur du registre avant le premier octet. Modbus : `0xFFFF` |
| `refin` | **true** : chaque octet est lu en commençant par son bit de poids **faible** (« réfléchi »). **false** : par le bit de poids fort. Les protocoles hérités des UART (Modbus, Kermit, zip) sont réfléchis |
| `refout` | **true** : le résultat final est réfléchi (ses bits sont retournés de bout en bout : bit 0 ↔ bit 15). Presque toujours égal à `refin` |
| `xorout` | Valeur combinée (XOR) avec le résultat final. `0` = rien ; `0xFFFFFFFF` pour crc32 (résultat inversé) |

**Pourquoi Modbus est-il souvent donné avec le polynôme `0xA001` ?** `0xA001` est `0x8005` réfléchi. Les documentations décrivent souvent l'algorithme « à l'envers » (registre décalé vers la droite, qui traite directement les bits de poids faible) : c'est exactement `poly 0x8005` avec `refin` et `refout` à true. Dans SerialHex, on écrit la forme normale `0x8005`, ou simplement `"crc16_modbus"`.

**Trouver les paramètres d'un CRC inconnu** : prendre une trame dont on connaît le CRC, puis essayer les noms prêts à l'emploi (champ Hexa libre + « Calc auto CRC », ou un calculateur en ligne). Si aucun ne convient, l'ordre des octets du CRC (`order`) ou la plage couverte (`over`) est souvent en cause.

## 5. Plage d'un CRC : `over`

`"over": [début, fin]`, bornes **incluses**.

| Borne | Valeur | Signification |
|---|---|---|
| début | entier | numéro d'octet (0 = premier octet de la trame) |
| début | nom de champ | premier octet de ce champ |
| fin | entier | numéro d'octet |
| fin | nom de champ | dernier octet de ce champ |
| fin | `"end"` | dernier octet juste avant le CRC |

| Exemple | Octets couverts |
|---|---|
| (absent) | toute la trame avant le CRC, comme `[0, "end"]` |
| `["SYNC", "LEN"]` | l'en-tête du protocole générique intégré |
| `["DATA", "DATA"]` | les données seules ; vide s'il n'y a pas de données |
| `[1, "end"]` | tout sauf le premier octet (octet de synchro exclu) |
| `[0, 10]` | les octets 0 à 10, pour une trame fixe |

Un champ nommé absent (DATA vide, champ `if` non rempli) donne une plage vide.

## 6. Taille des données

| Cas | Comment l'écrire | Exemple |
|---|---|---|
| Taille donnée par un champ longueur | un champ `length` avec `"of": "DATA"`, placé avant DATA | protocole générique : LEN sur 1 octet |
| Longueur qui compte aussi le CRC | `"of": ["DATA", "CRC"]` | `01 03 05 06 0F` : longueur 3 = 2 octets de données + 1 de CRC |
| Taille fixe | `"size": 10` sur DATA | trame fixe de 12 octets |
| Le reste de la trame | DATA sans `size` et sans champ longueur ; les champs suivants doivent avoir une taille fixe | `[SYNC][DATA…][CRC]` |
| Pas de données | `"size": 0` sur DATA, ou pas de champ `data` | trame de commande seule |

## 7. Conditions : `if`

`"if": "NOM"` : le champ n'existe que si le champ `NOM` est présent et :
- pour DATA : non vide ;
- pour un champ numérique (longueur, code d'erreur, champ libre…) : différent de 0 ;
- pour un octet fixe, un CRC ou des octets non lus : toujours vrai.

Exemples : `"DATA CRC" ... "if": "DATA"` (CRC des données seulement s'il y a des données) ; `"PAD" ... "role": "na", "if": "DATA"` (octets de bourrage après des données).

## 8. Placement des champs : `at` et `after`

Par défaut, les champs se suivent **dans l'ordre de la liste**. Chaque champ peut aussi dire où il se place ; on peut ainsi changer l'ordre sans réécrire la liste, ou décrire la trame comme le tableau d'une spécification (« octet 0 : SYNC, octets 2 à 5 : COMMAND ID… »).

| Clé | Valeur | Effet |
|---|---|---|
| `"at": 6` | numéro d'octet | le champ **commence à l'octet 6**. Les octets laissés libres avant lui deviennent automatiquement des octets non lus (`(octets 2-3)`, rôle `na`) |
| `"at": "start"` | | en **tête** de trame |
| `"at": "end"` | | en **fin** de trame (CRC final…) ; plusieurs champs `end` restent dans l'ordre de la liste |
| `"after": "NOM"` | nom d'un champ | **juste après** le champ NOM ; un champ placé après un autre l'accompagne s'il est lui-même déplacé (en cascade) |

Règles :
1. ordre de base : les champs `"at": "start"`, puis les champs sans placement (chacun suivi de ses champs `after`) ;
2. les champs à **octet fixe** sont prioritaires : ils prennent leur place, et les autres s'écoulent autour (avant eux s'ils tiennent entièrement, sinon après) ;
3. les champs `"at": "end"` ferment la trame.

Un octet fixe doit se trouver avant toute partie de taille variable (DATA, champ conditionnel `if`).

**Changer l'ordre sans réécrire la liste**

```json
"tx": [
  {"name": "CRC", "role": "crc", "algo": "sum16", "at": "end"},
  {"name": "DATA", "role": "data", "after": "LEN"},
  {"name": "CMD", "size": 2, "role": "command_id", "at": 4},
  {"name": "RID", "size": 1, "role": "request_id", "after": "SOF"},
  {"name": "LEN", "size": 1, "role": "length", "of": "DATA", "after": "CMD"},
  {"name": "SOF", "size": 1, "value": "0x7E", "at": "start"}
]
```

Ordre obtenu : `SOF` (octet 0) · `RID` (1) · `(octets 2-3)` non lus · `CMD` (4-5) · `LEN` (6) · `DATA` · `CRC`.

**Carte des octets, comme dans une spécification**

```json
"tx": [
  {"name": "SYNC",        "size": 1, "value": "0x7E", "at": 0},
  {"name": "COMMAND ID",  "size": 4, "role": "command_id", "at": 2},
  {"name": "HEADER CRC",  "size": 2, "role": "crc", "algo": "crc16_modbus", "at": 6, "over": [0, 5]}
]
```

L'octet 1, non décrit, devient `(octet 1)`, non lu.

| Message | Cause |
|---|---|
| `l'octet 1 est déjà occupé (les champs précédents vont jusqu'à l'octet 1)` | deux champs à octet fixe qui se chevauchent |
| `impossible de le placer à l'octet 3, le champ 'D' qui le précède n'a pas une taille fixe` | octet fixe après une partie de taille variable |
| `placement circulaire (after) : A, B` | A après B et B après A |
| `after désigne un champ inconnu 'Z'` | nom mal écrit |
| `"at" et "after" ne peuvent pas être utilisés ensemble` | un seul placement par champ |
| `le bit 2 est déjà occupé (les champs précédents vont jusqu'au bit 3)` | deux champs en bits qui se chevauchent |
| `une seule taille (size, LENb)` / `une seule position (at, atb)` | deux tailles ou deux positions pour un même champ |

## 8 bis. Champs en bits : `LENb`, `atb`, `bit_order`

Un champ peut faire un nombre de **bits** quelconque et commencer sur **n'importe quel bit** : drapeaux, numéro de version sur 3 bits, code de fonction sur 7 bits…

| Clé | En octets | En bits | Équivalence |
|---|---|---|---|
| Taille | `"size": 1` ou `"LENO": 1` | `"LENb": 8` | `LENO` × 8 = `LENb` |
| Position | `"at": 2` ou `"atO": 2` | `"atb": 16` | `atO` × 8 = `atb` |

**Numérotation des bits** (`bit_order` du fichier) :

| `bit_order` | Bit 0 | Lecture d'un champ de plusieurs bits | Usage |
|---|---|---|---|
| `msb` (défaut) | bit de **poids fort** de l'octet 0 | le premier bit lu est le poids fort de la valeur | schémas de spécification (« bits 0-2 : version »), en-têtes réseau |
| `lsb` | bit de **poids faible** de l'octet 0 | le premier bit lu est le poids faible | registres de microcontrôleurs, trames « Intel » |

Règles :
- un champ qui commence et finit sur des octets entiers est lu octet par octet, avec `byte_order` / `order` ; un champ en bits est lu bit par bit, avec `bit_order` ;
- DATA et les CRC font des octets entiers et commencent sur un octet ; un champ conditionnel (`if`) fait des octets entiers ; la trame finit sur un octet entier (sinon : `la trame ne finit pas sur un octet entier (il manque 4 bit(s))`) ;
- une longueur (`length`) compte des octets : les champs comptés doivent faire **ensemble** des octets entiers (un bit + 7 bits = 1 octet, comme l'octet de fonction Modbus TCP) ; le champ longueur lui-même peut être en bits ;
- les trous laissés par `atb` deviennent des bits non lus (`(bits 8-11)`) ; un champ `na` en bits est écrit à 0 (`fill` 0) ou à 1 (autre `fill`) ;
- position affichée « octet.bit » dans les tableaux (`1.0`, `1.1-1.7`) ; valeur en binaire (`5 (0b101)`) ;
- couleurs : un octet partagé entre plusieurs champs prend la couleur du dernier.

**Exemple : exception Modbus.** Dans une réponse, le bit de poids fort de l'octet de fonction signale une exception (`0x83` = exception sur la fonction 3). En le séparant (1 bit + 7 bits), la fonction reste la même que dans la requête ; avec deux variantes (§8 ter), l'octet qui suit devient le code d'erreur :

```json
"rx": {"variants": [
  {"name": "Normale", "fields": [
    {"name": "ADRESSE",   "size": 1, "role": "request_id", "color": "hdr"},
    {"name": "EXCEPTION", "LENb": 1, "role": "value", "value": 0},
    {"name": "FONCTION",  "LENb": 7, "role": "command_id", "color": "cmd"},
    {"name": "DATA",      "role": "data"},
    {"name": "CRC", "size": 2, "role": "crc", "algo": "crc16_modbus", "order": "little", "color": "crc"}]},
  {"name": "Exception", "fields": [
    {"name": "ADRESSE",   "size": 1, "role": "request_id", "color": "hdr"},
    {"name": "EXCEPTION", "LENb": 1, "role": "value", "value": 1},
    {"name": "FONCTION",  "LENb": 7, "role": "command_id", "color": "cmd"},
    {"name": "CODE EXCEPTION", "size": 1, "role": "error"},
    {"name": "CRC", "size": 2, "role": "crc", "algo": "crc16_modbus", "order": "little", "color": "crc"}]}
]}
```

`01 83 02 C0 F1` → variante Exception : ADRESSE 1, FONCTION 3, CODE EXCEPTION 2 (fond rouge, `erreur 2 (Adresse de données invalide)` d'après `errors`).

**Exemple : octet de commande découpé** (`bit_order` `msb`) :

```json
"tx": [
  {"name": "VERSION", "LENb": 3, "value": 2, "color": "hdr"},
  {"name": "TYPE",    "LENb": 5, "role": "command_id", "color": "cmd"},
  {"name": "URGENT",  "LENb": 1, "role": "field", "atb": 12},
  {"name": "SEQ",     "LENO": 1, "role": "request_id", "atO": 2}
]
```

`TYPE` 0x15 : octet 0 = `010 10101` = `0x55` ; `URGENT` au bit 12 (bit 4 de l'octet 1) : octet 1 = `0x08` ; les bits 8-11 et 13-15 sont des bits non lus.

## 8 ter. Plusieurs formats de trame : `variants`

Certains protocoles ont plusieurs formats de trame, reconnus à leurs octets fixes : M-Bus (`E5`, trame courte `10…16`, trame longue `68 L L 68…16`), PROFIBUS (SD1 à SD4), réponse normale / exception Modbus. `tx` et `rx` peuvent alors contenir une liste de **variantes** :

```json
"rx": {
  "variants": [
    {"name": "Accusé", "description": "Accusé E5", "description_en": "E5 acknowledge",
     "fields": [ {"name": "ACK", "size": 1, "role": "value", "value": "0xE5"} ]},
    {"name": "Longue",
     "fields": [ {"name": "START", "size": 1, "value": "0x68"}, … ]}
  ]
}
```

| Règle | Détail |
|---|---|
| Nom | `name` obligatoire et unique ; affiché dans la liste **Format** de l'onglet Protocole (requête) |
| Champs | chaque variante est une liste de champs complète, vérifiée comme un `tx` / `rx` simple ; les noms peuvent se répéter d'une variante à l'autre |
| Décodage | la variante est choisie d'après les **octets fixes** (`value`) ; si plusieurs conviennent, la première qui se décode sans erreur |
| Construction | la variante choisie dans la liste **Format**, ou celle de la commande (`"variant"` dans le `Msg_*.json`) ; la première par défaut |
| Résumés | REQUEST ID, COMMAND ID… sont cherchés dans la première variante qui en a un |

Une réponse sans REQUEST ID (accusé `E5`) arrête la surveillance de timeout de la plus ancienne requête en attente.

## 8 quater. Codage sur la ligne : `encoding`

Par défaut la trame est envoyée telle quelle (`"encoding": "binary"`). Modbus ASCII écrit chaque octet en deux caractères hexa, entre un début et une fin :

```json
"encoding": {"type": "ascii_hex", "start": ":", "end": "\r\n", "lowercase": false}
```

| Clé | Défaut | Rôle |
|---|---|---|
| `type` | `binary` | `binary` ou `ascii_hex` |
| `start` | `":"` | caractère(s) de début |
| `end` | `"\r\n"` | fin de trame ; sert aussi à **découper les trames reçues** dès son arrivée, sans attendre le silence |
| `lowercase` | `false` | hexa en minuscules |

Les champs, longueurs et CRC (LRC `sum8_2c`) portent sur la trame **binaire** ; l'aperçu et le moniteur colorent les caractères envoyés. Messages : `début de trame ':' absent`, `fin de trame '\r\n' absente`, `caractères hexa ASCII invalides`.

`01 03 00 00 00 0A` (LRC `F2`) part sous la forme `:01030000000AF2` CR LF.

## 9. Couleurs

| `color` | Affichage | Usage conseillé |
|---|---|---|
| `hdr` | gris clair | octets fixes et numéros de l'en-tête (synchro, adresse, REQUEST ID) |
| `cmd` | gras | identifiant de commande |
| `crc` | vert pastel (rouge si faux) | CRC et sommes |
| `na` | gris très clair barré | octets non lus (par défaut pour le rôle `na`) |
| `"#FF8800"` | cette couleur exactement | un champ que l'on veut repérer (une couleur par champ si besoin) |
| (rien) | couleur de la ligne (TX bleu, RX violet dans le moniteur) | données, longueurs |

Les couleurs réelles de `hdr`, `cmd`, `crc`, `na`, des erreurs et des lignes TX / RX se règlent dans l'interface : bouton **Couleurs…** (voir [GUI.md](GUI.md#couleurs)). Une couleur `"#RRGGBB"` écrite dans le fichier ne change pas avec ce réglage.

Le code d'erreur (rôle `error`) est toujours sur fond vert à 0, rouge sinon. Un octet fixe ou un CRC faux est en rouge, quelle que soit sa couleur. Les couleurs ne s'appliquent qu'à une trame complète.

## 9 bis. Textes lisibles : descriptions, valeurs, catégories

Pour qu'un fichier se lise sans la spécification sous les yeux :

```json
{"name": "FONCTION", "size": 1, "role": "command_id", "color": "cmd",
 "description": "Code fonction Modbus", "description_en": "Modbus function code",
 "values": {
   "0x03": {"fr": "Lecture de registres", "en": "Read Holding Registers"},
   "0x06": "Écriture d'un registre"
 }}
```

| Clé | Où | Affichage |
|---|---|---|
| `description` / `description_en` | fichier, variante, champ | colonne **Description** des tableaux, à côté de la liste des protocoles ; la version anglaise si l'interface est en anglais (repli sur le français) |
| `values` | champ numérique | à côté de la valeur décodée : `3 (0x03) Lecture de registres` ; clés en décimal ou hexa |
| `errors` | fichier | texte du code d'erreur ; texte simple ou `{"fr", "en"}` |
| `categories` | fichier | texte de la catégorie d'une commande (`"group": "READ"` → « Lecture — … » devant la description) |
| `category` | champ | étiquette libre, sans effet sur les octets |

Ces clés ne changent rien aux octets construits ou décodés.

## 10. Exemples complets

### Protocoles publics fournis

Les fichiers complets, commentés ligne à ligne, sont dans `protocols/`. Trames de référence (vérifiées par les tests) :

| Fichier | Trame | Signification |
|---|---|---|
| `modbus_rtu.json` | `01 03 00 00 00 02 C4 0B` | esclave 1, lecture de 2 registres à partir de 0 |
| | `01 03 04 00 E6 00 01 DA 04` | réponse : 2 registres, 0x00E6 et 0x0001 |
| | `01 83 02 C0 F1` | exception 2 (adresse invalide), variante Exception |
| `modbus_ascii.json` | `:01030000000AF2` CR LF | lecture de 10 registres, LRC `F2` |
| `modbus_tcp.json` | `00 01 00 00 00 06 01 03 00 00 00 0A` | transaction 1, longueur 6, unité 1 |
| `mbus.json` | `10 5B 05 60 16` | REQ_UD2 à l'adresse 5 (trame courte) |
| | `68 03 03 68 53 05 50 A8 16` | SND_UD, CI 0x50 : remise à zéro (trame longue, L répété) |
| | `E5` | accusé |
| `profibus_fdl.json` | `10 05 02 49 50 16` | SD1 : demande d'état FDL de l'esclave 5 par le maître 2 |
| | `68 05 05 68 85 82 6D 3C 3E EE 16` | SD2 : diagnostic DP, adresses avec bit d'extension, SAP 60 → 62 |

### SYNC sur 2 octets, numéro 16 bits, octets réservés, CRC32

```json
{
  "name": "Exemple CRC32",
  "byte_order": "big",
  "crc": { "c": "crc32" },
  "tx": [
    {"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
    {"name": "SEQ", "size": 2, "role": "request_id", "color": "hdr"},
    {"name": "RÉSERVÉ", "size": 2, "role": "na"},
    {"name": "CMD", "size": 1, "role": "command_id", "color": "cmd"},
    {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
    {"name": "DATA", "role": "data"},
    {"name": "CRC", "role": "crc", "algo": "c", "over": [2, "end"], "color": "crc"}
  ],
  "rx": [
    {"name": "SYNC", "size": 2, "value": "0xAA55", "color": "hdr"},
    {"name": "SEQ", "size": 2, "role": "request_id", "color": "hdr"},
    {"name": "RÉSERVÉ", "size": 2, "role": "na"},
    {"name": "STATUT", "size": 1, "role": "error"},
    {"name": "LEN", "size": 1, "role": "length", "of": "DATA"},
    {"name": "DATA", "role": "data"},
    {"name": "CRC", "role": "crc", "algo": "c", "over": [2, "end"], "color": "crc"}
  ],
  "errors": { "0": "OK", "1": "Commande inconnue", "2": "Paramètre invalide" }
}
```

Le CRC exclut le SYNC (`over` commence à l'octet 2).

### Trame fixe de 12 octets, CRC8 sur les octets 0 à 10

```json
{
  "name": "Trame fixe",
  "tx": [
    {"name": "STX", "size": 1, "value": 2, "color": "hdr"},
    {"name": "DATA", "role": "data", "size": 10},
    {"name": "CRC", "role": "crc", "algo": "crc8", "over": [0, 10], "color": "crc"}
  ],
  "rx": [
    {"name": "STX", "size": 1, "value": 2, "color": "hdr"},
    {"name": "DATA", "role": "data", "size": 10},
    {"name": "CRC", "role": "crc", "algo": "crc8", "over": [0, 10], "color": "crc"}
  ]
}
```

### Sans numéro de requête ni identifiant de commande

```json
{"name": "REQUEST ID", "size": 0, "role": "request_id"}
```

Un champ de taille 0 est absent de la trame : le champ correspondant est grisé dans l'onglet Protocole, la réponse est rattachée à la dernière requête envoyée et le timeout de réponse n'est pas surveillé.

## 11. Messages d'erreur au chargement

| Message (extrait) | Cause |
|---|---|
| `"tx" : liste de champs attendue` | `tx` ou `rx` absent ou vide |
| `byte_order doit valoir little ou big` | faute de frappe |
| `champ 'X' : "size" manquant` | taille obligatoire pour ce rôle |
| `champ 'X' : size doit valoir 0 à 4` | taille trop grande (0 à 255 pour `na`) |
| `champ 'X' : rôle 'truc' inconnu (…)` | rôle mal écrit |
| `noms en double : X` | deux champs de même nom dans `tx` (ou `rx`) |
| `un seul champ de rôle 'data'` | deux champs du même rôle unique |
| `CRC 'x' ni défini dans "crc" ni connu` | `algo` inconnu |
| `size 2 incompatible avec crc8 (1 octet(s))` | taille ≠ taille du CRC |
| `over désigne un champ inconnu 'X'` / `of …` / `"if" …` | nom de champ mal écrit |
| `la longueur 'L' doit précéder le champ 'DATA'` | champ longueur placé après ce qu'il compte |
| `value ne tient pas sur 1 octet(s)` | valeur fixe trop grande |
| `fill doit valoir 0 à 255 (un octet)` | octet de remplissage invalide |
| `après une DATA de taille variable, les champs doivent avoir une taille fixe` | DATA « le reste » suivie d'une autre partie variable |
| `JSON invalide (ligne 12) : …` | virgule ou guillemet manquant (les commentaires `//` sont acceptés) |
| `"rx" : chaque variante doit avoir un "name"` / `variantes en double : X` | variantes mal nommées (§8 ter) |
| `"same_as" manquant (champ recopié)` / `le champ recopié 'L' doit le précéder` | champ `copy` incomplet ou placé avant l'original |
| `encoding : type inconnu (binary ou ascii_hex)` | `encoding` mal écrit |
| `les champs comptés par of doivent faire ensemble des octets entiers (15 bits)` | longueur sur des champs en bits qui ne forment pas des octets entiers |

## 12. Lien avec les fichiers de commandes

Clés d'une commande utiles avec ces protocoles (détail : [PROTOCOLE.md](PROTOCOLE.md#une-commande)) :

| Clé | Exemple | Rôle |
|---|---|---|
| `variant` | `"Courte"` | format de trame de la requête (M-Bus, PROFIBUS) |
| `header` | `{"CI": "0x52"}` | valeurs de champs d'en-tête propres à la commande ; distingue des commandes au même COMMAND ID |
| `match` | `{"register": "0x0010"}` | valeurs de champs `tx` qui distinguent des commandes au même COMMAND ID (Modbus : même fonction, registre différent) |
| `name_en`, `description_en`, `label_en` | | textes en anglais |
| `attributes` | `{"access": "R"}` | champs libres affichés avec la description |
| `hidden` | `true` | commande masquée dans les listes, reconnue au décodage ([PROTOCOLE.md](PROTOCOLE.md#commandes-masquées-hidden)) |


Chaque fichier `Msg_*.json` indique pour quel protocole il a été écrit :

```json
{
  "protocol": "Modbus RTU",
  "group": "READ",
  "commands": [ … ]
}
```

- `protocol` : nom (`name` du fichier de protocole), ou liste de noms. Comparaison sans tenir compte des majuscules.
- Les commandes d'un fichier écrit pour **un autre** protocole sont ignorées (signalé dans le moniteur : `Msg_X.json ignoré : écrit pour le protocole …`, ou `N fichier(s) de commandes ignoré(s)` s'il y en a plusieurs).
- Sans clé `protocol`, le fichier convient à tous les protocoles.
- Dans l'onglet Manuel, le protocole visé est affiché sous la description du message (en orange s'il diffère du protocole en cours).
