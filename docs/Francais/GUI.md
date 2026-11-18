# Interface

[← Retour au README](../../README.md)

```
┌────────────────────── Liaison (série / TCP) ─────────────────────┐
├─ [Protocole] [Manuel] ─ [Langue] [Couleurs…] [x] ▶ Replay ─┬─ Replay ─┤
│  Protocole : requête / réponse  ·  Manuel : messages  │  (case)   │
├──────────────────────────── Moniteur ────────────────────────────┤
```

| Zone | Contenu |
|---|---|
| Onglet **Manuel** | À gauche la liste des messages JSON (Recharger, Charger…, Retirer, Délai, Envoyer la sélection), à droite les paramètres du message sélectionné |
| Onglet **Protocole** | Requêtes du protocole choisi (celui de `edition.json` au premier lancement) et décodage des réponses, voir [PROTOCOLE.md](PROTOCOLE.md) |
| Panneau **Replay** | Afficher, modifier, enregistrer et rejouer une trace CSV, voir [TRACE.md](TRACE.md) |

### Langue

La liste **Français / English**, à droite de la rangée d'onglets, choisit la langue de l'interface. Le choix est mémorisé (`settings.json`, clé `language`) et SerialHex propose de redémarrer pour l'appliquer. En anglais :

- tous les libellés, boutons et messages du moniteur sont traduits (fichier `ui/lang/en.json`, modifiable : un texte absent reste en français) ;
- les messages du moteur (CRC faux, trame tronquée, port occupé…) sont traduits d'après des modèles du même fichier ;
- les textes des fichiers de protocole et de commandes passent en anglais quand ils existent : `description_en`, `values` / `errors` / `categories` écrits `{"fr": …, "en": …}`, `name_en`, `description_en`, `label_en` des commandes.

### Replay

La case **▶ Replay**, à droite de la rangée d'onglets, affiche ou masque le panneau Replay : masqué, les onglets prennent toute la largeur ; affiché, la moitié droite de la fenêtre (séparateur déplaçable). Les flèches **→ Replay** des onglets Manuel et Protocole envoient la trame construite dans la ligne sélectionnée de la trace.

Les séparateurs entre les zones se déplacent à la souris. La taille de la fenêtre et la position des séparateurs sont **mémorisées** et retrouvées au lancement suivant (`settings.json`) ; le séparateur de chaque onglet est posé au premier affichage de cet onglet. Au premier lancement, la fenêtre fait 1720 × 920, la zone du haut prend environ 74 % de la hauteur et le moniteur 26 % ; dans l'onglet Protocole, la requête prend les deux tiers ; dans l'onglet Manuel, la liste des messages prend environ 30 % de la largeur (jamais moins de 150 px). Quand une nouvelle version change la disposition par défaut, la taille et les séparateurs mémorisés sont oubliés une fois (`layout_version`).

### Code couleur des trames

Le même code couleur est utilisé dans l'onglet Manuel, l'onglet Protocole et le moniteur :

| Couleur | Octets |
|---|---|
| gris clair | En-tête : octets fixes d'un message JSON ; champs `"color": "hdr"` du protocole (synchro, adresse, REQUEST ID) |
| **gras** | Champs `"color": "cmd"` du protocole (COMMAND ID) |
| bleu | DATA, dans les aperçus des onglets Manuel et Protocole et dans les champs de saisie de DATA (couleur des trames TX) ; dans le moniteur, DATA garde la couleur de la ligne |
| vert pastel | Checksum d'un message JSON ; champs `"color": "crc"` du protocole (HEADER CRC et DATA CRC) |
| fond vert / fond rouge | Code d'erreur d'une réponse : `00` (pas d'erreur) sur fond vert, tout autre code sur fond rouge |
| gris très clair barré | Octets non lus (rôle `na`) |
| rouge | Contrôle en échec (CRC incorrect, octet fixe faux) |

Pour le protocole, chaque champ choisit sa catégorie de couleur dans le fichier de protocole (`"color": "hdr"`…), ou une couleur exacte (`"color": "#FF8800"`) ; les couleurs ne s'appliquent qu'à une trame **complète**. Toutes ces couleurs se règlent avec le bouton **Couleurs…** (ci-dessous).

### Couleurs

Bouton **Couleurs…**, à droite de la rangée d'onglets (à côté de « ▶ Replay ») : page de réglage de toutes les couleurs de l'interface.

| Groupe | Couleurs |
|---|---|
| Moniteur et replay | Trames envoyées (TX, bleu), reçues (RX, violet), informations (gris), erreurs (rouge) ; les lignes TX / RX du tableau du replay suivent |
| Champs des trames | En-tête `hdr`, commande `cmd` (vide = couleur de la ligne, en gras), CRC `crc`, octets non lus `na`, CRC ou octet fixe faux, fonds du code d'erreur à 0 et non nul |

Pour chaque couleur :
- un **échantillon** de la couleur choisie (cliquer dessus ouvre la palette) ;
- le code **hexa** (`#1F5FBF`, ou `1F5FBF`), modifiable au clavier ; il reste en rouge tant qu'il n'est pas valide ;
- **Palette…** : sélecteur de couleur du système ;
- **Défaut** : couleur d'origine.

L'**aperçu** en bas montre des trames typiques (requête, réponse correcte, réponse en erreur avec CRC faux, octets non lus, informations) avec les couleurs en cours de réglage. **Appliquer** met à jour toute l'interface, y compris les lignes déjà affichées ; **OK** applique et ferme ; **Tout par défaut** remet les couleurs d'origine. Les couleurs sont mémorisées dans `settings.json`. Sur un fond de code d'erreur, le texte passe automatiquement en noir ou en blanc pour rester lisible.

## Liaison

Le panneau tient sur **deux lignes** :

```
Liaison (•) Série ( ) TCP   Port [COM3 — USB Serial Port ▾] [Actualiser] [x] FTDI ● libre   [Connecter] ● Déconnecté
Vitesse [115200] Données [8] Parité [Aucune] Stop [1] Flux [Aucun]      DTR RTS  Connexion auto…  TX 0 o RX 0 o
```

En TCP, la ligne 1 montre l'adresse et le port du serveur à la place du port série, et la ligne 2 n'a plus les réglages du port série.

| Élément | Rôle |
|---|---|
| **Liaison** | **Série** (port COM) ou **TCP** (Modbus TCP, passerelle série / Ethernet). Choix mémorisé ; impossible à changer pendant une connexion |
| **Adresse / Port** (TCP) | Serveur à joindre, `192.168.1.10` et `502` (Modbus TCP) par exemple ; mémorisés à la connexion |
| **Port** | Ports présents sur la machine, avec leur description (ex. `COM3 — USB-SERIAL CH340`) |
| **État du port** | Voyant à côté du port : **libre**, **occupé** par un autre programme, **absent** |
| **Actualiser** | Relit la liste des ports et re-teste le port sélectionné |
| **FTDI** | Ne montre que les adaptateurs de la liste `"filter"` d'`edition.json` (par défaut les FTDI : VID `0x0403`, PID `6001` FT232R, `6010` FT2232, `6011` FT4232, `6014` FT232H, `6015` FT-X). Choix mémorisé ; état au premier lancement : `"filter_default"`. Voir [Liste des ports](#liste-des-ports-editionjson) |
| **Vitesse** | Choisie dans la liste ou saisie au clavier (valider avec Entrée) |
| **Données / Parité / Stop / Flux** | Format de la liaison, 8N1 sans contrôle de flux par défaut |
| **Connecter / Déconnecter** | Juste après l'état du port. Ouvre / ferme le port ; un voyant (plus gros et vert une fois connecté) et le texte indiquent l'état (`Connecté — COM3 @ 115200 8N1`) |
| **DTR / RTS** | Pilotage manuel des lignes de contrôle une fois connecté |
| **TX / RX** | Nombre d'octets envoyés / reçus depuis la connexion |
| **Connexion auto au démarrage** | Se reconnecte tout seul au dernier port utilisé au lancement suivant |

### Liste des ports (`edition.json`)

La clé `"ports"` d'`edition.json` règle la liste des ports série :

```jsonc
"ports": {
  "hide_bluetooth": true,       // ports série sur Bluetooth jamais affichés
  "filter_label": "FTDI",       // texte de la case de filtre
  "filter_default": true,       // case cochée au premier lancement (mémorisée ensuite)
  "filter": [                   // adaptateurs gardés quand la case est cochée
    {"name": "FT232R / FT245R", "vid": "0x0403", "pid": "0x6001", "enabled": true},
    {"name": "CH340",           "vid": "0x1A86", "pid": "0x7523", "enabled": false}
  ]
}
```

- `"enabled": false` retire un adaptateur du filtre sans effacer sa ligne ; pour un autre adaptateur, ajouter une ligne avec son VID et son PID (visibles dans le Gestionnaire de périphériques : `USB\VID_0403&PID_6001`).
- Les ports **Bluetooth** (Windows : « Lien série standard sur Bluetooth », `BTHENUM` ; Linux : `/dev/rfcomm*` ; macOS : `/dev/cu.Bluetooth*`) sont retirés de la liste, que la case soit cochée ou non, si `"hide_bluetooth"` vaut `true` (valeur par défaut).
- Clé absente : Bluetooth masqué, filtre FTDI décoché.

- La liste des ports se met à jour toute seule quand un adaptateur est branché ou débranché.
- Les changements de réglages pendant une connexion sont **appliqués immédiatement** au port, sans se déconnecter.
- Si le câble est retiré ou si le port tombe en erreur, la déconnexion est détectée et signalée dans le moniteur.
- Le port est ouvert **sans activer DTR ni RTS** : une carte Arduino / ESP32 ne redémarre pas à la connexion.
- En **TCP**, les octets reçus sont découpés en trames comme sur un port série (silence « Fin de trame après … ms ») ; DTR / RTS et les réglages de format sont sans objet. Une fermeture de la connexion par l'appareil est signalée comme une perte de liaison.
- Protocole avec une **fin de trame** (Modbus ASCII : CR LF) : chaque trame reçue est coupée dès son délimiteur, sans attendre le silence.
- Les derniers réglages sont mémorisés dans `settings.json` et rechargés au lancement. Le **dernier port** utilisé (connecté ou simplement choisi dans la liste) est resélectionné ; le moniteur indique « Dernier port utilisé : COM3 », ou qu'il est absent.

## Onglet Manuel

### Messages (à gauche)

- Les messages sont rangés par groupe, un groupe par fichier `msgLibrary/msgManual/Msg_<fonction>.json` (voir [MESSAGES.md](MESSAGES.md)).
- **Clic** : affiche les paramètres du message.
- **Double-clic** : envoie le message.
- **Ctrl / Maj + clic** : sélection multiple. **Envoyer la sélection** envoie les messages dans l'ordre, séparés par le délai indiqué (ms).
- **Recharger** : relit le dossier `msgLibrary/msgManual/` et les fichiers ajoutés après une modification des fichiers.
- La liste ne contient que les messages présents dans les fichiers : on y met les trames les plus pratiques, toutes prêtes, pour gagner du temps. Les commandes du protocole se choisissent dans l'onglet Protocole.
- Un **message de protocole** (sauvegardé avec le bouton **Sauvegarder…** de l'onglet Protocole, ou écrit avec la clé `request`) montre REQUEST ID, COMMAND ID et DATA, **modifiables** : la trame est reconstruite par le protocole en cours, longueur (DATA LENGTH) et CRC compris. DATA s'écrit en bleu, et le nombre d'octets s'affiche en direct à droite (`hex · 9 octet(s) → DATA LENGTH = 9`). Voir [MESSAGES.md](MESSAGES.md#message-de-protocole-request).
- **Valeur convertie** (message de protocole) : sous DATA, la section **Valeur** montre DATA convertie d'après la commande du protocole en cours qui a ce COMMAND ID. Un champ par valeur : liste déroulante pour un choix (`off` / `on`), nombre en unité réelle, IP, texte… Les **données prédéfinies** de la commande sont proposées à côté. Les deux sens sont synchronisés en direct : modifier DATA met à jour les valeurs, modifier une valeur recalcule DATA sur le bon nombre d'octets. Champs **en vert** : conversion connue. **En bleu** : pas de conversion (COMMAND ID inconnu, ou commande sans DATA décrite) ; DATA est alors lue comme un entier non signé (ordre d'octets du protocole), et une valeur saisie est réécrite sur le nombre d'octets de DATA (plus si elle ne tient pas). La case **Hexa** affiche les entiers en hexa (`0x05DC`) au lieu du décimal (par défaut). Une valeur invalide, ou une DATA de mauvaise taille, est signalée en rouge à droite.
- **Charger…** : ajoute des fichiers JSON situés ailleurs. **Doublons** : un fichier déjà chargé n'est pas relu, un message identique à un message déjà présent (copie d'un fichier sous un autre nom…) est ignoré ; deux messages de même nom dans le même groupe mais différents sont gardés tous les deux, le nom du fichier d'origine entre crochets les distingue (`Lire état  [Msg_Banc.json]`). La liste des fichiers ajoutés est **mémorisée** (`settings.json`, `message_files`) : ils restent affichés après une sauvegarde, **Recharger** ou au lancement suivant ; **Retirer** enlève de la liste les fichiers ajoutés des messages sélectionnés (rien n'est effacé du disque ; les fichiers de `msgLibrary/msgManual/` restent toujours affichés).
- Tant que la liaison n'est pas connectée, **Envoyer**, **Répéter toutes les** et **Envoyer la sélection** sont grisés (comme Envoyer de l'onglet Protocole et l'**Hexa libre** du moniteur).

### Paramètres (à droite)

- Sous la description : « Écrit pour : Modbus RTU », le protocole pour lequel le fichier du message a été écrit (clé `"protocol"`), en orange s'il diffère du protocole en cours.
- **→ Replay** : la trame du message, avec les valeurs saisies, va dans la ligne sélectionnée du replay.

- Un formulaire est généré pour le message sélectionné : champ texte, liste déroulante ou case à cocher selon le type.
- Les entiers acceptent le décimal (`12`), l'hexa (`0x0C`) ou le binaire (`0b1100`).
- La **trame** est recalculée à chaque modification, checksum compris, et affichée en couleurs : octets fixes en gris, checksum en vert. Une valeur invalide ou hors limites s'affiche en rouge.
- **Envoyer** : envoie la trame une fois.
- **Répéter toutes les … ms** : envoi périodique, arrêté automatiquement en cas de déconnexion ou de changement de message.

## Protocole

Onglet dédié au protocole requête / réponse de l'appareil :

- **Protocole** : liste des fichiers du dossier `protocols/` (`Modbus RTU (modbus_rtu.json)`), avec leur description à côté. Le choix est mémorisé ; il change la structure des trames (champs, tailles, CRC, couleurs) partout : onglet, moniteur, hexa libre, timeout. Un fichier invalide est signalé dans le moniteur et marqué ⚠ dans la liste. Format : [PROTOCOLE.md](PROTOCOLE.md#fichier-de-protocole-protocols).

- **Requête** (partie haute, **CMD TX**) : choisir une commande de la bibliothèque (on tape dans la liste pour chercher, les propositions s'ouvrent ; ☆ ajoute aux **Favoris**, affichés sous CMD TX ; un Get a aussi un bouton **Envoyer** à droite du COMMAND ID ) ; ses champs de DATA apparaissent en bleu dans le tableau de la trame, avec leur valeur par défaut, et se **modifient directement dans le tableau** (clic sur la colonne Valeur). Pour un protocole à plusieurs formats de trame (M-Bus, PROFIBUS), la liste **Format** choisit la variante ; une commande qui précise la sienne (`"variant"`) la sélectionne d'elle-même. La trame complète (longueur et CRC compris) est détaillée en dessous. La ligne **DATA** (en bleu) se modifie aussi, en **hexa brut** : les champs montrent alors le décodage de ces octets (un champ modifié ensuite change ses octets dans la DATA brute ; DATA vidée ou données prédéfinies : retour aux valeurs des champs). Boutons : **Sauvegarder…** (demande le nom du message, le fichier proposé `Msg_<nom>.json` s'affichant en direct, puis ouvre l'explorateur sur `msgLibrary/msgManual/` avec ce fichier pré-rempli, modifiable ; préfixe `Msg_` ajouté au besoin ; groupe « Sauvegardés » ; un fichier hors de `msgLibrary/msgManual/` est chargé quand même ; nom déjà pris dans le fichier : remplacer, garder les deux (« nom (2) ») ou annuler ; identique : rien n'est écrit), **Copier** et **Envoyer** (grisé tant que la liaison n'est pas connectée). La case **REQ+** (infobulle « auto req_id ») incrémente le REQUEST ID après chaque envoi. Saisie manuelle possible (COMMAND ID + DATA en hexa).
- **Réponse (RX)** : chaque trame reçue (ou collée) est décodée : en-tête, code d'erreur avec son texte, champs de DATA en unité physique. La colonne **Valeur** ajoute le sens de la valeur (`values` du fichier : `3 (0x03) Lecture de registres`), la colonne **Description** la description du champ. Le **type de réponse** est trouvé automatiquement d'après le REQUEST ID, ou choisi à la main.
- **Ordre des octets** : celui du fichier de protocole (`byte_order`).
- Les tableaux de la requête et de la réponse occupent toute la place restante (la requête les deux tiers au premier lancement). Le séparateur entre requête et réponse se déplace à la souris.

Détails : [PROTOCOLE.md](PROTOCOLE.md).

## Moniteur

| Élément | Rôle |
|---|---|
| Journal | `TX` en bleu, `RX` en violet, informations en gris, erreurs en rouge, horodatés à la milliseconde. Les octets de DATA gardent la couleur de la ligne ; seuls l'en-tête, le COMMAND ID, le code d'erreur et les CRC ont leur propre couleur. Les lignes ne sont pas coupées : barre de défilement horizontale en bas pour voir la fin des longues lignes |
| **ASCII** | Affiche la version texte de chaque trame |
| **Afficher TX** | Masque les trames envoyées pour ne voir que la réception |
| **Défilement auto** | Suit les dernières lignes |
| Couleurs | En-tête en gris, COMMAND ID en gras, CRC en vert (voir le code couleur plus haut) |
| **● Trace** | Enregistre toutes les trames TX / RX dans un fichier CSV horodaté ; cliquer à nouveau pour arrêter. Voir [TRACE.md](TRACE.md) |
| **+ Replay** | Copie les trames du moniteur (TX et RX, avec leurs temps) dans le panneau Replay, comme une nouvelle trace à rejouer ; sans trame, affiche seulement le panneau. Voir [TRACE.md](TRACE.md) |
| **Décoder protocole** | Ajoute un résumé à chaque trame du protocole choisi (reconnue à ses octets fixes, `A5 5A` pour le protocole générique) : « réponse #0x05 · erreur 0 · 2 o · CRC OK », puis en fin de ligne, en **gras** (couleur de la ligne : bleu en TX, violet en RX), la valeur de chaque champ de DATA convertie selon le JSON (type, facteur, offset, unité, choix, bits) : `=> Consigne = 23.0 °C`. En rouge si la valeur est hors min / max ou si un bit d'erreur est actif |
| **Fin de trame après … ms de silence** | Les octets reçus sont regroupés en une seule trame tant que le silence entre eux est plus court que ce délai |
| **Timeout réponse … ms** | Délai maximal (500 ms par défaut, mémorisé) entre une requête du protocole et sa réponse, reconnue par son REQUEST ID (protocole sans REQUEST ID : pas de surveillance). Sans réponse à temps, une ligne rouge s'affiche : `TIMEOUT : pas de réponse en 500 ms à « Lire consigne et mode #0x03 » (REQUEST ID 0x03)`. Utilisé aussi par le replay |
| **Effacer / Sauvegarder…** | Vide le journal / enregistre ses trames en **trace CSV** rejouable (`.csv`, par défaut dans `traces/`, à ouvrir dans le panneau Replay) ou son texte en `.txt` |
| **Hexa libre** | Envoie les octets saisis (`AA 55 01 0D`, `AA55010D` ou `0xAA,0x55`) ; grisé tant que la liaison n'est pas connectée |
| **Calc auto CRC (crc16_modbus)** | Calcule le CRC principal du protocole choisi (CRC16 Modbus pour Modbus RTU) sur les octets saisis et l'ajoute en fin de trame à l'envoi |
| Aperçu | Sous le champ : la trame exacte qui partira, en couleurs. Case cochée : CRC calculé (derniers octets) en rouge ; case décochée : la trame telle que collée. Trame du protocole complète : en-tête gris, COMMAND ID gras, CRC vert (rouge s'il est faux) |

## Terminal en ligne de commande

Pour un usage rapide sans interface :

```bash
python tools/hexterm.py           # liste les ports disponibles
python tools/hexterm.py COM3      # 115200 bauds par défaut
python tools/hexterm.py COM3 9600
```

Taper les octets (`AA 55 01 0D`) puis Entrée, `q` pour quitter.

## Dépannage

| Problème | Solution |
|---|---|
| Port indiqué « occupé » | Fermer Tera Term ou l'autre programme qui l'utilise, puis **Actualiser** |
| Aucun port dans la liste | Vérifier le câble et le driver USB-série (CH340, CP210x, FTDI…) ; décocher le filtre **FTDI** pour un autre adaptateur |
| Liste des messages vide dans l'onglet Manuel | Déplacer le séparateur au bord gauche de l'onglet ; vérifier le moniteur (« … message(s) chargé(s) depuis msgLibrary/msgManual/ ») |
| `No module named 'serial'` | `pip install -r requirements.txt` (le paquet s'appelle `pyserial`, pas `serial`) |
| `No module named 'tkinter'` | Linux : `sudo apt install python3-tk` |
| Accès refusé sous Linux | `sudo usermod -aG dialout $USER`, puis se reconnecter |
| Rien reçu | Vérifier vitesse et format, câblage TX/RX croisé et masse commune |
| Envoi bloqué avec RTS/CTS | L'appareil ne gère pas le contrôle de flux : repasser **Flux** sur « Aucun » |
| Trames reçues coupées en morceaux | Augmenter « Fin de trame après … ms de silence » |
| Requête refusée / valeurs incohérentes | Vérifier dans le moniteur que le HEADER CRC est vert (trame complète et CRC juste) |
| Changement de parité refusé | Certains adaptateurs n'acceptent pas tous les formats à chaud : se déconnecter et reconnecter |
