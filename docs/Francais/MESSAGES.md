# Fichiers de messages

[← Retour au README](../../README.md)

## Principe

- Les messages sont décrits dans des fichiers JSON placés dans le dossier `msgLibrary/msgManual/`.
- **Un fichier par fonction**, nommé `Msg_<fonction>.json` : `Msg_Moteur.json`, `Msg_Capteurs.json`…
- Au lancement, tous les fichiers `Msg_*.json` sont chargés et fusionnés (l'ancien préfixe `Message_` est encore accepté). Chaque fichier devient un groupe dans la liste.
- Après une modification, cliquer sur **Recharger** dans l'interface.
- Un fichier invalide est signalé dans le moniteur sans empêcher les autres de charger.

> Les **commandes du protocole** de l'appareil (partie TX / RX, unités, facteurs) et les **codes d'erreur** se décrivent aussi dans ces fichiers, sous les clés `"commands"` et `"errors"`, un ou plusieurs fichiers par appareil (`Msg_Regulateur_Exemple.json`) : voir [PROTOCOLE.md](PROTOCOLE.md).

## Exemple

`msgLibrary/msgManual/Msg_Moteur.json` :

```json
{
  "group": "Moteur",
  "messages": [
    {
      "name": "Régler vitesse",
      "description": "Consigne de vitesse en tr/min",
      "frame": ["AA 55", "20", "{moteur}", "{vitesse}", "{sens}", "{cs}"],
      "params": {
        "moteur":  { "type": "u8", "default": 1, "min": 1, "max": 4 },
        "vitesse": { "type": "u16be", "default": 1500, "min": 0, "max": 3000, "unit": "tr/min" },
        "sens":    { "type": "enum", "choices": { "avant": 0, "arriere": 1 } }
      },
      "checksum": { "algo": "xor8", "start": 2 }
    },
    {
      "name": "Arrêt",
      "frame": ["AA 55 21 00", "{cs}"],
      "checksum": { "algo": "xor8", "start": 2 }
    }
  ]
}
```

Avec les valeurs par défaut, « Régler vitesse » donne `AA 55 20 01 05 DC 00 F8`.

## Structure d'un fichier

| Clé | Obligatoire | Rôle |
|---|---|---|
| `group` | non | Nom affiché du groupe. Par défaut : le nom du fichier après `Msg_`. Utile pour les accents (`Msg_Systeme.json` → `"Système"`) |
| `messages` | oui | Liste des messages |
| `protocol` | non | Protocole pour lequel le fichier a été écrit (`"Modbus RTU"`, ou une liste de noms). Information affichée dans l'onglet Manuel ; pour les commandes (`"commands"`), un fichier écrit pour un autre protocole est ignoré. Voir [CONF_PROTOCOLE.md §12](CONF_PROTOCOLE.md#12-lien-avec-les-fichiers-de-commandes) |

## Structure d'un message

| Clé | Obligatoire | Rôle |
|---|---|---|
| `name` | oui | Nom affiché dans la liste |
| `frame` | oui (sauf message de protocole) | Composition de la trame (voir ci-dessous) ; ou `request` : [message de protocole](#message-de-protocole-request) |
| `description` | non | Texte d'aide affiché au-dessus des paramètres |
| `params` | non | Définition des paramètres utilisés dans `frame` |
| `checksum` | non | Calcul du checksum, si `{cs}` apparaît dans `frame` |
| `group` | non | Force le groupe pour ce message uniquement |

## Message de protocole (`request`)

Au lieu de décrire les octets avec `frame`, un message peut donner seulement ce que l'onglet Protocole demande : la trame est alors **construite par le protocole en cours** (longueur, CRC d'en-tête et de DATA compris).

```json
{
  "name": "Écrire l'état marche",
  "description": "Commande 0x8010, DATA = 01",
  "request": {
    "request_id": 5,
    "command_id": "0x8010",
    "data": "01"
  }
}
```

| Clé de `request` | Obligatoire | Rôle |
|---|---|---|
| `command_id` | oui | COMMAND ID (`"0x80010001"` ou nombre) |
| `request_id` | non | REQUEST ID (absent : protocole sans REQUEST ID) |
| `data` | non | DATA en hexa (`""` = pas de données) |
| `header` | non | Autres champs d'en-tête, par nom ou rôle : `{"CI": "0x52"}` |
| `variant` | non | Format de trame, pour un protocole à variantes (`"Longue"`) |

- Dans l'onglet Manuel, **REQUEST ID**, **COMMAND ID** et **DATA** s'affichent comme des paramètres **modifiables** ; la trame (en couleurs du protocole) suit chaque modification, CRC compris.
- Le bouton **Sauvegarder…** de l'onglet Protocole enregistre la requête affichée dans ce format : il demande le nom du message (le fichier proposé, `Msg_<nom>.json`, s'affiche en direct : espaces remplacés par `_`), puis ouvre l'explorateur sur `msgLibrary/msgManual/` avec ce fichier pré-rempli, que l'on peut encore changer (préfixe `Msg_` ajouté au besoin ; un fichier créé ainsi a le groupe « Sauvegardés »). Choisir un fichier existant y ajoute le message. Si le nom existe déjà dans le fichier : **Oui** le remplace, **Non** garde les deux (le nouveau devient « nom (2) »), **Annuler** n'écrit rien ; un message identique n'est pas réécrit. Un fichier choisi hors de `msgLibrary/msgManual/` est chargé quand même et mémorisé avec les fichiers ajoutés par **Charger…** (`settings.json`, `message_files`) : la liste de l'onglet Manuel reste complète après la sauvegarde et au lancement suivant ; **Retirer** l'en enlève. Ce fichier est réécrit par SerialHex : le renommer pour garder ses propres commentaires.
- **Doublons au chargement** : un message identique à un message déjà chargé (le groupe ne compte pas : copie d'un fichier sous un autre nom) est ignoré ; deux messages de même nom dans le même groupe mais différents sont gardés, avec le nom du fichier d'origine entre crochets dans la liste.
- Sous DATA, la section **Valeur** convertit DATA dans les deux sens d'après la commande du protocole en cours (champs en vert), ou la lit comme un entier si la commande est inconnue (en bleu) ; case **Hexa** pour les entiers. Voir [GUI.md](GUI.md#messages-à-gauche).
- La trame dépend du protocole choisi : « Écrit pour » apparaît en orange si le message a été écrit pour un autre protocole.

## Trame (`frame`)

Liste de morceaux concaténés dans l'ordre :

| Morceau | Signification |
|---|---|
| `"AA 55"` | octets fixes en hexa (espaces facultatifs) |
| `"{nom}"` | valeur du paramètre `nom` |
| `"{cs}"` | emplacement du checksum |

## Paramètres (`params`)

### Types

| Type | Taille | Saisie |
|---|---|---|
| `u8` / `i8` | 1 octet | `12`, `0x0C`, `0b1100` |
| `u16be` / `u16le` / `i16be` / `i16le` | 2 octets | `512`, `0x0200` |
| `u32be` / `u32le` / `i32be` / `i32le` | 4 octets | `100000` |
| `bool` | 1 octet (0/1) | case à cocher |
| `enum` | selon `size` (défaut `u8`) | liste déroulante |
| `hex` / `raw` | variable | `DE AD BE EF` (octets bruts, sans conversion) |
| `ascii` | variable, ou fixe avec `length` | `HELLO` |

`be` = big endian (octet de poids fort en premier), `le` = little endian.

### Options

| Option | Types | Rôle |
|---|---|---|
| `label` | tous | Libellé affiché (par défaut : le nom du paramètre) |
| `default` | tous | Valeur initiale |
| `min` / `max` | entiers | Bornes vérifiées avant l'envoi |
| `unit` | tous | Unité affichée à côté du champ |
| `choices` | `enum` | Dictionnaire `{"libellé": valeur}` |
| `size` | `enum` | Type de l'octet envoyé (`u8`, `u16be`…) |
| `length` | `ascii` | Longueur fixe, complétée par des `00` |

## Checksums (`checksum`)

```json
"checksum": { "algo": "xor8", "start": 2 }
```

| `algo` | Description | Taille |
|---|---|---|
| `xor8` | XOR de tous les octets | 1 octet |
| `sum8` | somme sur 8 bits | 1 octet |
| `sum8_2c` | complément à 2 de la somme | 1 octet |
| `crc8` | CRC-8 (polynôme 0x07) | 1 octet |
| `crc16_modbus` | CRC-16 Modbus | 2 octets, little endian |

`start` : index du premier octet inclus dans le calcul. Exemple : `2` pour exclure l'en-tête `AA 55`. Le calcul s'arrête juste avant `{cs}`.

## Fusionner les fichiers

Pour regrouper tous les fichiers en un seul, par exemple pour le partager :

```bash
python serialhex.py --merge
```

Crée `messages_merged.json` à la racine du projet, chargeable via le bouton **Charger…**. Chaque message garde son groupe.
