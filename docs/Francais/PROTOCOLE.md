# Protocole requête / réponse

[← Retour au README](../../README.md)

SerialHex sait construire et décoder les trames d'un protocole requête / réponse. La **structure des trames** (champs, tailles, CRC, couleurs) n'est pas codée en dur : elle est décrite dans un **fichier de protocole** du dossier `protocols/`. Les **commandes** de l'appareil sont décrites dans des fichiers JSON (`Msg_*.json`), avec une partie **TX** (ce qu'on envoie) et une partie **RX** (ce qu'on reçoit).

| Fichier | Rôle |
|---|---|
| `protocols/*.json` | Structure des trames, un fichier par protocole ([CONF_PROTOCOLE.md](CONF_PROTOCOLE.md), aide-mémoire `protocols/LISEZMOI_CONF.txt`) |
| `core/protocol/` | Moteur : lit le fichier de protocole, construit, décode, vérifie les CRC |
| `core/commands/` | Bibliothèque de commandes (TX / RX), codes d'erreur, unités et conversions |
| `ui/protocol/` | Onglet **Protocole** |
| `msgLibrary/msgList/…/Msg_*.json` | Commandes et codes d'erreur ; dossier indiqué par la clé `"commands"` du fichier de protocole |

## Fichier de protocole (`protocols/`)

Un fichier par protocole. Il décrit, champ par champ, la trame de **requête** (`tx`) et la trame de **réponse** (`rx`) : taille de chaque champ (en octets ou en bits), rôle (octet fixe, REQUEST ID, COMMAND ID, longueur, code d'erreur, CRC, DATA, champ libre, octets non lus, champ recopié), CRC 8 / 16 / 32 bits sur la plage d'octets voulue, plusieurs formats de trame, codage ASCII, couleurs et textes lisibles. Le protocole utilisé se choisit en haut de l'onglet **Protocole** ; le choix est mémorisé. **Recharger** (onglet Manuel) relit aussi le fichier après une modification.

**Toutes les options, avec descriptions et exemples : [CONF_PROTOCOLE.md](CONF_PROTOCOLE.md).**

Sans fichier utilisable, SerialHex utilise un **protocole générique intégré** (`SYNC A5 5A | SEQ | CMD | LEN | CRC8 | DATA | CRC16`, voir `core/protocol/default.py`).

## Bibliothèque de commandes (JSON)

Les commandes se décrivent dans les fichiers `Msg_*.json` du dossier indiqué par `"commands"` dans le fichier de protocole, sous la clé `"commands"`. Un même fichier peut contenir des `"messages"` (trames libres, voir [MESSAGES.md](MESSAGES.md)), des `"commands"` et des `"errors"`.

### Organisation des fichiers

- Un fichier par appareil, par fonction ou par commande : tous les `Msg_*.json` du dossier sont lus, dans l'ordre alphabétique.
- Sans clé `"group"` dans le fichier, le groupe (catégorie) est la fin du nom : `Msg_Mesures.json` → `Mesures`.
- Fournis avec la version Techmelec : `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json` (toutes les fonctions Modbus standard, génériques, pour n'importe quel appareil) et `msgLibrary/msgList/modbus/Msg_Regulateur_Exemple.json` (régulateur de température fictif).
- Une commande précise (avec `"match"`) et une commande générique (sans `"match"`) peuvent avoir le même COMMAND ID : au décodage, la précise passe en premier, la générique sert de repli (ex. fonction 03 : « Lire consigne et mode » pour le registre 0x0000, « 03 Lire registres de maintien » pour les autres).

### Structure d'un fichier

Extrait de `msgLibrary/msgList/modbus/Msg_Regulateur_Exemple.json` :

```jsonc
{
  "protocol": ["Modbus RTU", "Modbus ASCII", "Modbus TCP"],   // protocoles visés
  "group": "READ",
  "commands": [
    {
      "name": "Écrire consigne",
      "name_en": "Write setpoint",
      "id": "0x06",                                  // fonction Modbus = COMMAND ID
      "group": "WRITE",
      "description": "Registre 0x0000 ; la réponse est l'écho de la requête",
      "match": {"register": "0x0000"},               // distingue les autres commandes 06
      "tx": [
        {"name": "register", "label": "Registre", "type": "uint16", "default": "0x0000", "min": 0, "max": 0},
        {"name": "setpoint", "label": "Consigne", "type": "int16", "factor": 0.1, "unit": "°C",
         "min": -50, "max": 150, "default": 23}
      ],
      "rx": [
        {"name": "register", "label": "Registre", "type": "uint16"},
        {"name": "setpoint", "label": "Consigne", "type": "int16", "factor": 0.1, "unit": "°C"}
      ],
      "presets": [
        {"name": "20 °C", "values": {"setpoint": 20}}
      ]
    }
  ]
}
```

Avec `setpoint = 37.5`, la requête est `01 06 00 00 01 77 C8 7C` (375 en int16 big endian).

Les fichiers `Msg_*.json` acceptent les commentaires `//` et `/* */`, comme les fichiers de protocole. Une clé à `null` compte comme absente : on peut écrire chaque champ avec **tous ses paramètres** et laisser à `null` ceux qui ne servent pas.

`"protocol"` indique pour quel protocole le fichier a été écrit (nom, ou liste de noms). Les commandes d'un fichier écrit pour un autre protocole sont ignorées, avec un message dans le moniteur ; sans cette clé, le fichier convient à tous les protocoles. Détails : [CONF_PROTOCOLE.md §12](CONF_PROTOCOLE.md#12-lien-avec-les-fichiers-de-commandes).

### Une commande

| Clé | Obligatoire | Rôle |
|---|---|---|
| `name` | oui | Nom affiché |
| `id` | oui | COMMAND ID (`"0x06"`, `"0x80000004"` ou nombre) ; unique, sauf commandes distinguées par `match`, `header` ou `variant` |
| `presets` | non | Données prédéfinies proposées dans le menu « Données » |
| `description` | non | Texte affiché sous la commande |
| `tx` | non | Champs de DATA de la **requête**, dans l'ordre ; vide = pas de données envoyées |
| `rx` | non | Champs de DATA de la **réponse**, dans l'ordre ; vide = pas de données attendues |
| `group` | non | Groupe (catégorie) ; par défaut celui du fichier. Texte lisible dans `categories` du fichier de protocole |
| `name_en` / `description_en` | non | Nom et description en anglais (interface en anglais) |
| `variant` | non | Format de trame de la requête, pour un protocole à variantes (M-Bus `"Courte"` / `"Longue"`, PROFIBUS `"SD1"`…) |
| `header` | non | Valeurs des champs d'en-tête propres à la commande, par nom ou rôle : `{"CI": "0x52"}`. Deux commandes au même COMMAND ID se distinguent ainsi |
| `match` | non | Valeurs de champs `tx` qui distinguent des commandes au même COMMAND ID (Modbus : même fonction 03, registres différents) : `{"register": "0x0010"}`. Le champ prend cette valeur par défaut |
| `attributes` | non | Champs libres affichés après la description : `{"access": "R", "level": "expert"}` |
| `hidden` | non | `true` : commande **masquée**, voir ci-dessous |

Un même COMMAND ID ne peut être utilisé qu'une fois, sauf si les commandes se distinguent par `match`, `header` ou `variant`, ou si l'une d'elles est masquée. La réponse est décodée avec la commande de la requête envoyée sous le même REQUEST ID (onglet Protocole : la commande choisie ; trame d'une autre origine : retrouvée d'après le COMMAND ID et `match` / `header`).

### Commandes masquées (`hidden`)

Une commande avec `"hidden": true` n'apparaît pas dans les listes « Commande » et « Type de réponse » de l'onglet Protocole, mais elle reste **reconnue au décodage** : une trame qui l'utilise est résumée avec son nom dans le moniteur. Utile pour les commandes obsolètes, internes ou commentées dans le code de l'appareil, qu'on veut identifier sans encombrer les listes.

- La case **« Masquées (n) »**, à droite de la liste des commandes, les ajoute aux listes (choix mémorisé ; la case n'apparaît que s'il y a des commandes masquées).
- `"hidden": true` au niveau du fichier masque toutes ses commandes ; une commande peut s'en écarter avec `"hidden": false`.
- Une commande masquée peut avoir le même COMMAND ID qu'une commande visible (ancien nom d'une commande réutilisée) : la visible est prioritaire au décodage.
- Le moniteur indique au chargement : `Protocole : 1000 commande(s) masquée(s), visibles avec la case « Masquées »`.

```json
{"name": "Ancienne mesure", "id": "0x000C", "hidden": true, "attributes": {"état": "obsolète"}}
```

### Un champ (dans `tx` ou `rx`)

| Clé | Rôle | `null` / absent |
|---|---|---|
| `name` | Nom du champ (unique dans la liste) | obligatoire |
| `label` | Libellé affiché, si différent de `name` | `name` |
| `label_en` | Libellé en anglais (interface en anglais) | `label` |
| `type` | Format des données, voir tableau ci-dessous | `uint8` |
| `count` | Taille du tableau : `U8[4]` → `"type": "uint8", "count": 4` | 1 (pas un tableau) |
| `unit` | Unité affichée : `"%"`, `"°C"`, `"mW"`… | aucune |
| `factor` | Facteur de conversion | 1 |
| `offset` | Décalage | 0 |
| `min` / `max` | Plage autorisée, **en unité réelle** ; vérifiée à l'envoi, signalée en rouge au décodage | **limites du type**, calculées automatiquement |
| `default` | Valeur par défaut, en unité réelle (requête) | 0, ou le premier choix |
| `decimals` | Nombre de décimales affichées | déduit de `factor` et `offset` |
| `format` | Saisie / affichage d'un tableau : `"ip"` (`192.168.1.10`) ou `"mac"` (`00:1A:2B:3C:4D:5E`) | valeurs séparées par des virgules |
| `choices` | Liste de choix `{ "libellé": valeur }` sur un entier : menu déroulant. Valeur en décimal ou en texte hexa (`"0xFF00"`) | saisie libre |
| `bits` | Champ de bits `{ "numéro de bit": "nom" }` : les bits à 1 sont listés par leur nom | entier normal |
| `length` | `ascii` / `hex` : taille fixe en octets ; `bcd` : nombre d'octets | taille variable ; 4 pour `bcd` |

**Conversion** : `valeur réelle = valeur brute × factor + offset`.

| Exemple | Saisie | Brut envoyé |
|---|---|---|
| `uint16`, `factor: 0.1`, unité mW | `12.5` | 125 |
| `int16`, `factor: 0.01`, unité °C | `-5.25` | -525 |
| `uint16`, `factor: 0.001`, `offset: 2.5`, unité V | `3.3` | 800 |

Les valeurs décimales acceptent le point ou la virgule (`12,5`). La valeur brute est arrondie à l'entier le plus proche.

### Min / Max automatiques

Si `min` ou `max` vaut `null`, la limite est **calculée d'après le type**, puis convertie en unité réelle avec le facteur et l'offset :

| Type | `factor` / `offset` | Plage automatique |
|---|---|---|
| `uint8` | — | 0 à 255 |
| `int16` | — | -32768 à 32767 |
| `uint8` | `factor: 0.1` | 0.0 à 25.5 |
| `uint16` | `factor: 0.001`, `offset: 2.5` | 2.500 à 68.035 |
| `float`, choix, bits, texte | — | pas de limite automatique |

Dans l'onglet Protocole, la colonne **Description** du tableau affiche la plage appliquée, toujours en unité réelle (du JSON, ou calculée d'après le type). Une valeur hors du type est refusée avec un message en unité réelle : `30 hors limites du type uint8 (0.0 mW à 25.5 mW)`.

### Types de champs (data format)

| Type | Aussi accepté | Taille | Remarque |
|---|---|---|---|
| `uint8`, `int8` | `u8`, `i8`, `U8` | 1 | entier non signé / signé |
| `uint16`, `int16` | `u16`, `i16` | 2 | ordre du protocole (`byte_order`) |
| `uint32`, `int32` | `u32`, `i32` | 4 | ordre du protocole : `0x12345678` → `12 34 56 78` |
| `uint16be`, `int32le`… | `u16be`, `i32le`… | 2 / 4 | ordre des octets forcé pour ce champ |
| `float` | `f32`, `float32`, `F32` | 4 | flottant IEEE 754 |
| `bool` | | 1 | case à cocher, 0 / 1 |
| `ascii` | | `length`, ou variable | texte ; complété par des `00` si `length` |
| `raw` | `hex`, `RAW` | `count` (ou `RAW[n]`), ou variable | **octets bruts, sans conversion** : saisis et affichés en hexa |
| `bcd` | | `length` (4 par défaut) | chiffres décimaux, 2 par octet (n° d'identification M-Bus : `12345678` → `78 56 34 12` en little endian) ; `factor` / `unit` possibles ; un chiffre > 9 s'affiche « BCD invalide » |
| `enum` | | selon `size` | ancienne écriture d'un choix ; préférer un entier avec `choices` |

Les majuscules sont acceptées, et la taille d'un tableau peut aussi s'écrire dans le type, comme dans la documentation : `"type": "U8[4]"` équivaut à `"type": "uint8", "count": 4`. Un champ de taille variable (`ascii` / `hex` sans `length`) n'est autorisé qu'en **dernier**.

### Tableaux

| Documentation | JSON | Saisie / affichage |
|---|---|---|
| `U8[4]` (adresse IP) | `{ "type": "uint8", "count": 4, "format": "ip" }` | `192.168.1.100` |
| `U8[6]` (adresse MAC) | `{ "type": "uint8", "count": 6, "format": "mac" }` | `00:1A:2B:3C:4D:5E` |
| `F32[2]` | `{ "type": "float", "count": 2, "unit": "mm" }` | `-1000, 2500.5` → `[-1000, 2500.5] mm` |
| `U32[2]` + bits | `{ "type": "uint32", "count": 2, "bits": { ... } }` | liste des bits à 1 |

Sans `format`, les valeurs se séparent par des virgules, des espaces ou des points-virgules.

### Octets bruts (raw)

Pour une donnée sans conversion (ni facteur, ni unité, ni choix), utiliser `raw` : la valeur est saisie et affichée directement en hexa.

| JSON | Saisie | Remarque |
|---|---|---|
| `{ "name": "data", "type": "raw", "count": 4 }` | `01 02 03 04` | 4 octets exactement ; défaut `00 00 00 00` |
| `{ "name": "data", "type": "RAW[4]" }` | `01 02 03 04` | même chose, écriture de la documentation |
| `{ "name": "data", "type": "raw" }` | `01 02 03 …` | nombre d'octets libre : seulement en **dernier** champ |

Pour `raw`, `count` est le **nombre d'octets** (et non un tableau). Plusieurs champs `raw` de taille fixe peuvent se suivre.

### Champ de bits

Un entier (ou un tableau d'entiers) avec `"bits"` est décodé en liste des bits à 1. Pour un tableau, le mot 0 porte les bits 0 à 31, le mot 1 les bits 32 à 63, etc. Exemple, mot d'alarmes sur 2 × 32 bits :

```json
{ "name": "alarmes", "type": "uint32", "count": 2,
  "bits": { "0": "Défaut interne", "1": "Porte ouverte", "32": "Température hors plage" } }
```

Affichage : `0x0000000100000003 : Défaut interne, Porte ouverte, Température hors plage`, en rouge dès qu'un bit est à 1 ; un bit à 1 sans nom s'affiche `bit N`.

### Données prédéfinies

Une commande peut proposer des jeux de valeurs, choisis dans la liste des **données prédéfinies** de l'onglet (affichée sur la ligne du REQUEST ID, seulement si la commande en a) :

```json
"presets": [
  { "name": "Marche", "values": { "état": "marche" } },
  { "name": "Arrêt",  "values": { "état": "arrêt" } }
]
```

Les champs absents d'un preset gardent leur valeur par défaut. Après le choix d'un preset, les champs restent modifiables à la main (le menu repasse alors sur « saisie à la main »). Chaque preset est vérifié au chargement.

### Codes d'erreur

Clé `"errors"`, dans n'importe quel fichier `Msg_*.json`, ou dans le fichier de protocole (prioritaire). Un texte peut être bilingue : `"4": {"fr": "Commande inconnue", "en": "Unknown command"}`.

```json
{
  "errors": {
    "0": "OK",
    "4": "Commande inconnue",
    "6": "Paramètre hors limites"
  }
}
```

Les codes peuvent aussi s'écrire en hexa (`"0x04"`). Le texte s'affiche à côté du code d'erreur (champ de rôle `error`) dans le décodage et dans le moniteur.

### Vérifications au chargement

Une définition invalide est signalée dans le moniteur (et la commande ignorée) : type inconnu, `factor` à 0, `choices` manquant, champ en double, taille variable ailleurs qu'en dernier, valeur par défaut hors plage, COMMAND ID en double.

## Onglet Protocole

### Requête (TX)

La partie haute de l'onglet (sans titre) prépare la requête :

1. **CMD TX** : choisir une commande de la bibliothèque (`WRITE / Écrire consigne (0x06)`), ou « saisie manuelle ». **On peut taper dans la liste pour chercher** : un clic dans le champ sélectionne tout le texte, on tape directement, et les **propositions s'ouvrent sous le champ** dès la première lettre (nom, catégorie ou COMMAND ID : `consigne`, `READ`, `0x1E` trouve le Get `0x0000001E` et le Set `0x8000001E`) ; ↑ / ↓ pour s'y déplacer, Entrée ou clic pour choisir ; champ vidé ou Échap : la commande en cours réapparaît. **Favoris** : le bouton **☆** à droite de la liste ajoute la commande en cours aux favoris (**★** : la retire) ; s'il y en a au moins un, la liste **Favoris** apparaît sous CMD TX (3 lignes visibles, défilement au-delà) et un clic y choisit la commande. Les favoris sont mémorisés par protocole (`settings.json`, `favorite_commands`). Pour un **Get** (bit 31 du COMMAND ID à 0), un bouton **Envoyer** apparaît aussi à droite du COMMAND ID, juste sous la liste (même action que le bouton Envoyer du bas). Les listes sont rangées par **opcode** : COMMAND ID croissant sur ses 31 bits de poids faible, le Get (bit 31 à 0) avant le Set (bit 31 à 1), quel que soit le fichier ou le nom. Pour un protocole à plusieurs formats de trame, la liste **Format** choisit la variante. La case **Masquées (n)** ajoute à la liste les commandes `"hidden"` ([voir plus haut](#commandes-masquées-hidden)).
2. **Ligne REQUEST ID / COMMAND ID** : on y trouve aussi la liste des **données prédéfinies** (si la commande en a), la description de la commande, et à droite **Sauvegarder…** et **Copier**. Les valeurs se modifient **dans le tableau de la trame**.
3. Avec une commande : COMMAND ID est rempli, et chaque champ `tx` apparaît **en bleu** sous la ligne DATA du tableau. **Clic sur la colonne Valeur** (ou double-clic sur la ligne, ou Entrée) : la valeur se modifie sur place ; Entrée ou clic ailleurs valide, **Tab** passe au champ suivant, Échap annule. Un champ à choix (ou booléen) propose une liste. La colonne **Description** rappelle le type et la conversion, la plage en unité réelle (du JSON, ou d'après le type) et la valeur par défaut. Une valeur invalide reste affichée en rouge avec « invalide : … », le message d'erreur remplace la trame hexa et l'envoi est bloqué.
   La ligne **DATA** (en bleu) se modifie de la même façon, en **hexa brut** (`FF 33 33 53 70 61 72 6B`) : la trame utilise ces octets tels quels et les champs affichent leur décodage. Un champ modifié ensuite remplace ses octets dans la DATA brute (s'il garde la même taille ; sinon retour aux valeurs des champs). DATA vidée, ou données prédéfinies choisies : retour aux valeurs des champs. En saisie manuelle, DATA se saisit en hexa sur la ligne DATA du tableau.
   **Valeur brute ou convertie** : un champ se modifie aussi dans sa colonne **Hexa**, en octets bruts (même taille ; `00 00 00 40` pour un float32 de 2,0) : la DATA devient alors une DATA brute et les champs montrent son décodage. Les bornes (min / max) et le type sont rappelés dans la colonne Description. Les tableaux de la requête et de la réponse prennent la hauteur de leurs lignes (toute la trame visible) et le séparateur se place tout seul ; la trame hexa occupe toute la largeur (sur plusieurs lignes si besoin), avec les boutons juste en dessous.
4. En saisie manuelle : COMMAND ID en hexa, et DATA en hexa sur la ligne **DATA** du tableau. **Envoyer** et **→ Replay** sont au bout de la ligne de la trame hexa.
5. La **trame complète** est détaillée en dessous, champ par champ (les champs de DATA apparaissent sous la ligne DATA, avec leur valeur physique).
6. **Sauvegarder…** demande un nom (le fichier proposé `Msg_<nom>.json` s'affiche en direct), puis ouvre l'explorateur avec ce fichier pré-rempli dans `msgLibrary/msgManual/`, modifiable, et enregistre la requête (REQUEST ID, COMMAND ID, DATA, brute ou issue des champs) comme message de l'onglet Manuel ; nom déjà pris dans le fichier : remplacer, garder les deux ou annuler : on la renvoie ensuite en un clic, en modifiant la DATA si besoin ([message de protocole](MESSAGES.md#message-de-protocole-request)). **Copier** met la trame hexa dans le presse-papiers ; **Envoyer** l'envoie (grisé tant que la liaison n'est pas connectée) ; **→ Replay** la met dans la ligne sélectionnée de la trace du panneau Replay (insérée après, ou à la place, voir [TRACE.md](TRACE.md)).
7. **REQUEST ID** s'affiche et se saisit en hexa (`0x05`, sur la taille du champ ; le décimal est aussi accepté). Avec la case **REQ+** (infobulle « auto req_id »), il s'incrémente après chaque envoi réussi (0xFF → 0x00 sur 1 octet). Les résumés du moniteur l'écrivent de même : `requête #0x05`.

Les libellés REQUEST ID et COMMAND ID prennent les noms du fichier de protocole ; un champ absent du protocole (taille 0) est grisé.

Les valeurs saisies sont conservées pour chaque commande quand on passe de l'une à l'autre.

### Réponse (RX)

- Avec **« Suivre les réponses reçues »**, chaque trame reçue est décodée automatiquement. On peut aussi coller une trame et cliquer **Décoder** (choisir Requête ou Réponse).
- **Type de réponse** :
  - **Auto** : SerialHex retient le COMMAND ID de chaque requête envoyée (depuis l'onglet, la liste de messages ou l'hexa libre) avec son REQUEST ID ; à la réception, la réponse est décodée avec la partie `rx` de cette commande.
  - **Une commande** choisie dans la liste : force le décodage avec sa partie `rx`.
  - **Brut** : DATA affichée sans décodage.
- Le tableau affiche l'en-tête, le code d'erreur avec son texte (vert si 0, rouge sinon), et chaque champ de DATA avec sa valeur physique (unité comprise) et sa valeur brute.
- DATA **sans définition** (commande inconnue, sans champ `rx`, ou champ en octets bruts) : les lectures possibles sont ajoutées, pour 1 à 8 octets : entier (`DC 05` = `1500 (0x05DC)`, ordre d'octets du protocole), entier signé si le bit de poids fort est à 1, flottant sur 4 octets s'il est vraisemblable (`00 00 96 42` = `float 75`).
- Le résumé indique la commande utilisée et comment elle a été trouvée : `[type : Lire température, auto]`.
- Signalés en rouge : CRC incorrect, trame tronquée, octets en trop, DATA plus courte que prévu ou non décrite, valeur hors plage, code d'erreur ≠ 0.

### Moniteur

Avec **« Décoder protocole »**, chaque trame du protocole est résumée ; en fin de ligne, en gras (bleu en TX, violet en RX), la **valeur convertie** de chaque champ de DATA (type, facteur, offset, unité, choix, bits du JSON), jusqu'à 8 champs séparés par `|` :

```
TX  01 03 00 00 00 02 C4 0B      « requête #0x01 · Lire consigne et mode · 4 o · CRC OK »   => Registre = 0  |  Nombre = 2
RX  01 03 04 00 E6 00 01 DA 04   « réponse #0x01 · Lire consigne et mode · 5 o · CRC OK »   => Nombre d'octets = 4  |  Consigne = 23.0 °C  |  Mode = auto (1)
TX  01 06 00 00 01 77 C8 7C      « requête #0x01 · Écrire consigne · 4 o · CRC OK »   => Registre = 0  |  Consigne = 37.5 °C
RX  01 04 04 00 D7 01 F4 4B AB   « réponse #0x01 · Lire mesures · 5 o · CRC OK »   => Nombre d'octets = 4  |  Température = 21.5 °C  |  Humidité = 50.0 %HR
RX  01 83 02 C0 F1               « réponse #0x01 · Lire consigne et mode · erreur 2 (Adresse de données invalide) · CRC OK »
```

- La valeur est en **rouge** si elle sort de min / max, ou si un bit d'un champ `bits` est à 1 (`=> Relais = 0x01 : relais d'alarme actif`).
- L'octet du **code d'erreur** d'une réponse est sur fond **vert** à `00`, sur fond **rouge** pour tout autre code ; dans le résumé, `erreur N (texte)` est alors écrit en **rouge** (de même qu'un CRC faux ou une trame tronquée). Les autres octets de la réponse gardent leurs couleurs : c'est la **requête** que l'appareil a refusée.
- Une réponse en erreur n'affiche pas de valeur : sa DATA n'a pas le format normal.

### Hexa libre + CRC

- Case **« Calc auto CRC (crc16_modbus) »** : le CRC principal du protocole (celui du premier champ CRC de la requête, CRC16 Modbus pour Modbus RTU) est calculé sur les octets saisis et ajouté en fin de trame à l'envoi, dans l'ordre d'octets du protocole.
- Sous le champ, l'**aperçu** montre la trame exacte qui partira, en couleurs :
  - case cochée : octets saisis + CRC calculé, ses **octets en rouge** ;
  - case décochée : la trame telle que saisie ou collée ;
  - dès que c'est une trame du protocole **complète** : couleurs du fichier de protocole (en-tête gris, COMMAND ID gras, CRC vert s'il est juste, rouge s'il est faux).

## Utilisation dans un script

```python
from core.commands import load_library, encode_fields, decode_fields, describe
from core.protocol import load_protocol, QUERY, RESPONSE

proto = load_protocol("protocols/modbus_rtu.json")
lib = load_library(proto.commands_dir, proto.name)          # dossier "commands" du fichier

cmd = lib.find(0x06, bytes.fromhex("00 00"), proto)          # Écrire consigne (registre 0)
data = encode_fields(cmd.tx, {"setpoint": 37.5}, proto)
frame = proto.build_query(request_id=1, command_id=cmd.id, data=data)    # 01 06 00 00 01 77 C8 7C
# autre forme : proto.build(QUERY, data, request_id=1, command_id=cmd.id)

get = lib.find(0x03, bytes.fromhex("00 00 00 02"), proto)    # Lire consigne et mode
d = proto.decode(reponse, RESPONSE)
print(describe(d, get, lib))             # réponse #0x01 · Lire consigne et mode · 5 o · CRC OK
print(d.request_id, d.error, d.ok)       # champs repérés par leur rôle, quel que soit leur nom
fields, problems = decode_fields(get.rx, d.data.raw, proto)
for f in fields:
    print(f.name, f.text)                # Consigne 23.0 °C …
```

Même moteur en TypeScript pour le GUI React : `parseProtocol()` dans le paquet `js/` (voir [INTERFACE.md](INTERFACE.md)).

Tests : `tests/test_protocol.py`, `tests/test_protocol_vectors.py`, `tests/test_commands.py`. Les vecteurs `tests/protocol_vectors.json` (générés par `tools/gen_protocol_vectors.py`) sont vérifiés à l'identique par Python et par TypeScript (`js/test/protocol.test.ts`).
