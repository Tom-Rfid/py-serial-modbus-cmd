# Trace et replay

[← Retour au README](../../README.md)

SerialHex peut **enregistrer** toutes les trames envoyées et reçues dans un fichier horodaté (la trace), la **modifier** dans le panneau Replay, puis **rejouer** les envois de cette trace avec le même rythme, en comparant les réponses reçues aux réponses enregistrées.

| Fichier | Rôle |
|---|---|
| `core/trace/` | Enregistrement, relecture, analyse des temps, comparaison ; `document.py` : règles de modification et de renommage |
| `ui/replay/` | Panneau « Replay » : affichage, modification, détail de ligne, replay |
| `traces/` | Dossier proposé pour les traces (ignoré par Git) |

## Enregistrer une trace

1. Dans le moniteur, cliquer **● Trace** et choisir le fichier (par défaut `traces/trace_AAAAMMJJ_HHMMSS.csv`).
2. Utiliser SerialHex normalement : toutes les trames TX et RX sont enregistrées, quelle que soit leur origine (onglet Manuel, onglet Protocole, hexa libre, replay).
3. Cliquer **■ Arrêter la trace**. Le moniteur indique le nombre de trames et le fichier, et la trace s'ouvre dans le panneau **Replay**, affiché à droite (sauf si une autre trace y est en cours de modification).

Chaque trame est écrite immédiatement sur le disque : rien n'est perdu si le programme est fermé pendant l'enregistrement.

### Format du fichier

CSV, séparateur `;`, lisible et modifiable dans Excel :

```
t_ms;delta_ms;dir;len;hex;label
0.0;0.0;TX;8;01 03 00 00 00 02 C4 0B;Lire consigne et mode #0x01
41.9;41.9;RX;9;01 03 04 00 E6 00 01 DA 04;
264.5;222.6;TX;8;01 04 00 00 00 02 71 CB;Lire mesures #0x01
```

| Colonne | Contenu |
|---|---|
| `t_ms` | Temps depuis le début de l'enregistrement, en ms |
| `delta_ms` | Temps depuis la ligne précédente, en ms (pour lecture) |
| `dir` | `TX` (envoyé) ou `RX` (reçu) |
| `len` | Nombre d'octets |
| `hex` | Les octets |
| `label` | Nom du message envoyé (TX), facultatif |

Une trace peut aussi s'écrire à la main : seules `dir` et `hex` sont obligatoires (`t_ms` absent = 0 ms d'écart), le séparateur `,` est accepté, et les lignes commençant par `#` sont des commentaires.

## Rejouer une trace

1. Se connecter au port série.
2. Cocher **▶ Replay** à droite des onglets (ou bouton **+ Replay** du moniteur, qui y copie aussi les trames du moniteur) : le panneau s'affiche sur la moitié droite. Puis **Ouvrir…** (une trace enregistrée, ou un `.csv` fait par **Sauvegarder…** du moniteur).
3. Chaque ligne du fichier s'affiche dans le tableau (TX en bleu, RX en violet), avec l'**analyse des temps** au-dessus :
   `Durée 1.06 s · 5 TX · 4 RX · écart entre envois (min / moy / max) 264 / 266 / 267 ms · latence de réponse 42 / 52 / 62 ms · sans réponse : 1`
4. Choisir le **rythme** :
   - **Temps d'origine** : chaque requête part avec le même écart que dans la trace, avec une vitesse de x0.25 à x4 (x2 = deux fois plus vite) ;
   - **Délai fixe** : le même délai entre toutes les requêtes.
   La colonne « Délai » montre, sur chaque ligne TX, le délai appliqué avant son envoi.
5. Boutons de lecture, sous la barre d'édition : **⏭ Pas à pas** (bleu), **▶ Rejouer** (vert), **■ Arrêter** (rouge) ; une infobulle explique chacun au survol. **▶ Rejouer** : les lignes TX sont renvoyées une à une ; la ligne en cours porte l'icône **▶**. Les lignes RX ne sont pas envoyées, elles servent de référence.
   **Pas à pas** : **⏭ Pas à pas** envoie la requête de la ligne sélectionnée (ou la première), puis le bouton devient **⏭ Suivant** : chaque clic (ou **F8**) envoie la requête suivante, sans délai automatique. Le résultat d'une requête s'affiche au bout du timeout, ou tout de suite si l'on clique Suivant avant. **■ Arrêter** quitte le pas à pas.
6. **Timeout réponse** (500 ms par défaut, repris du moniteur) : délai maximal entre l'envoi d'une requête et sa réponse. Une réponse plus tardive ne compte pas. Après la dernière requête, SerialHex attend aussi ce délai pour les dernières réponses.

### Tableau

Une ligne par ligne du fichier. Un échange = une ligne TX et les lignes RX qui la suivent (réponses attendues) ; le résultat du replay s'affiche sur la ligne TX.

| Colonne | Contenu |
|---|---|
| (icône) | ▶ en cours d'envoi, puis le résultat : ✓, ≠, ✗, + |
| t (ms) | Instant de la ligne dans la trace |
| Dir | TX (envoyée) ou RX (reçue) |
| Octets (hexa) / Libellé | Contenu de la ligne |
| Résultat | Comparaison, voir ci-dessous |
| Délai | Attente avant l'envoi au replay (lignes TX), en ms |
| Réponse reçue / Lat. | Réponse obtenue au replay et sa latence |

Le panneau étant à demi-largeur, les dernières colonnes s'atteignent avec la barre de défilement horizontale (ou en élargissant le panneau avec le séparateur).

### Ligne sélectionnée : aide à la relecture

Cliquer une ligne affiche son détail sous le tableau :

```
Ligne 4 · TX · t 624.8 ms · depuis la précédente 113.1 ms · jusqu'à la suivante 62.5 ms · Lire mesures #0x01
01 04 00 00 00 02 71 CB              (couleurs du protocole : en-tête gris, COMMAND ID gras, CRC vert)
requête #0x01 · Lire mesures · 4 o · CRC OK   => valeurs converties
                                                          [Décoder dans Protocole]
```

- l'**intervalle** avec la ligne du dessus et celle du dessous ;
- la trame en couleurs et son décodage par le protocole en cours (commande, code d'erreur, valeurs converties) ;
- **Décoder dans Protocole** : une ligne **TX** (requête complète du protocole en cours) est chargée dans la partie **Requête** : commande retrouvée d'après son COMMAND ID, REQUEST ID et DATA (brute, les champs montrent son décodage), modifiable puis renvoyable. Une ligne **RX** (ou une TX qui n'est pas une requête du protocole) s'affiche dans la partie **Réponse**, décodée champ par champ (« Suivre les réponses reçues » est alors décoché pour qu'elle reste affichée). Le cadre rempli passe sur le **fond gris foncé** du Replay ; les deux cadres reviennent en gris clair dès qu'on choisit une nouvelle commande dans CMD TX.
- Case **Décoder** (à côté de **Comparer**) : même chose à chaque clic sur une ligne du tableau, sans passer par le bouton (rien n'est chargé pendant un replay).
- **■ Arrêter** est grisé tant que rien ne tourne ; **▶ Rejouer** est grisé pendant un replay ou un pas à pas.

| Résultat | Icône | Couleur | Signification |
|---|---|---|---|
| identique | ✓ | — | Mêmes octets, reçus avant le timeout |
| différent | ≠ | **fond orange** | Octets en cause : `octets 8-9 : attendu 80 BB, reçu 00 C8` |
| timeout | ✗ | **fond rouge** | Une réponse était attendue, rien reçu dans le « Timeout réponse » (une réponse tardive est signalée : `réponse arrivée après 620 ms`) |
| réponse en trop | + | fond jaune | Réponse reçue alors que la trace n'en a pas |
| aucune attendue | ✓ | — | Ni attendue, ni reçue |

Le résumé final compte les résultats : `Replay terminé : 3 identique, 1 différent, 1 aucune attendue`. Décocher « Comparer les réponses » pour rejouer sans comparaison.

### Modifier la trace

| Action | Comment |
|---|---|
| Modifier une cellule | **Double-clic** sur t, Dir, Octets ou Libellé ; **Entrée** valide, **Échap** annule. Une saisie invalide (hexa, nombre) est signalée et le champ reste ouvert |
| Ajouter une ligne | **+ Ajouter** : ligne TX après la sélection, **« Délai fixe » ms après** la ligne du dessus (les lignes suivantes sont décalées d'autant), avec les octets de la ligne du dessus ; la saisie des octets s'ouvre |
| Ajouter depuis un onglet | **→ Replay** (onglet Protocole : la requête construite ; onglet Manuel : le message avec ses valeurs). Selon le choix « → : insère après / remplace » de la barre d'édition, la trame est **insérée après** la ligne sélectionnée (au milieu de l'intervalle) ou **remplace** la ligne sélectionnée (son temps est gardé). Le libellé reprend le nom de la commande ou du message |
| Supprimer | **Supprimer** ou touche **Suppr** (sélection multiple avec Ctrl / Maj) |
| Déplacer | **Monter** / **Descendre** : la ligne change de place mais les temps restent dans l'ordre (les deux lignes échangent leur contenu, pas leur t) |
| Renommer / enregistrer | Le **Nom** du fichier se modifie directement (sans `.csv`). **Enregistrer** (ou Entrée) enregistre sous ce nom, dans le même dossier : si le nom a changé, le fichier est **renommé** ; si un autre fichier porte déjà ce nom, SerialHex demande s'il faut le **remplacer**. Un `*` signale des modifications non enregistrées ; SerialHex le rappelle avant d'ouvrir une autre trace ou de quitter |
| Enregistrer sous… | Copie dans un autre dossier ; l'original est gardé |
| Nouvelle | Trace vide, à remplir avec **+ Ajouter** ou les flèches **→ Replay** ; nom proposé `new_trace_<date>_<heure>` (modifiable), aussi utilisé si le champ Nom est vide à l'enregistrement |

Le replay utilise la trace affichée, enregistrée ou non. On ne peut pas la modifier pendant un replay.

### À savoir

- Une réponse est rattachée à la **dernière requête envoyée** : si l'appareil répond plus lentement que l'écart entre deux requêtes, sa réponse est comptée pour la suivante. Ralentir le replay (x0.5) ou utiliser un délai fixe plus long.
- Le replay renvoie exactement les octets enregistrés, REQUEST ID compris.
- Les valeurs qui changent d'elles-mêmes (températures, compteurs) apparaissent en « différent » : c'est attendu, la colonne Résultat indique les octets concernés.
- Les trames envoyées par le replay passent par le moniteur et, si une trace est en cours, sont enregistrées : on peut tracer un replay pour le comparer ensuite.

## Utilisation dans un script

```python
from core.trace import load_trace, exchanges, analyze, replay_delays, compare

events = load_trace("traces/essai.csv")
print(analyze(events).text())
for x, delay in zip(exchanges(events), replay_delays(exchanges(events), speed=2)):
    print(f"attendre {delay:.0f} ms puis envoyer {x.tx.data.hex(' ')}")
print(compare(bytes.fromhex("01 03 02 12 34"), bytes.fromhex("01 03 02 12 35")))
# (False, 'octet 4 : attendu 34, reçu 35')

# Modifier une trace sans l'interface (mêmes règles que le panneau Replay)
from core.trace import TraceDocument
doc = TraceDocument("traces")
doc.load("traces/essai.csv")
row = doc.insert_after(2, "TX", bytes.fromhex("01 03 00 02 00 01 25 CA"), "ajoutée")  # t au milieu
doc.set_cell(0, "label", "Lire puissance")
doc.save_as_name("essai_v2")          # renomme ; FileExistsError si le nom est pris
```

Tests : `tests/test_trace.py`.
