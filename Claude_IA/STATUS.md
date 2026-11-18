# STATUS — état du projet SerialHex (version Techmelec)

> Mis à jour le 2026-11-18. Consignes : [CLAUDE.md](CLAUDE.md).

## État

- Tests Python : 111 OK (`python -m pytest -q`) ; paquet TypeScript `js/` : tests vitest OK (vecteurs partagés avec Python).
- Protocoles fournis : Modbus RTU / ASCII / TCP, M-Bus, PROFIBUS FDL, et `exemple_generique.json` (modèle à copier).
- Appareils d'exemple fictifs : régulateur de température (Modbus), compteur d'énergie (M-Bus), module d'E/S (PROFIBUS).

## Fonctions en place

**Liaison** (panneau sur 2 lignes)
- Série ou TCP ; filtre des ports par VID / PID (`"ports"` d'edition.json, liste activée / désactivée ; case « FTDI »), ports Bluetooth masqués ; voyant de connexion ; reconnexion auto ; détection de la perte du port.
- Tant que la liaison n'est pas connectée, tous les boutons d'envoi sont grisés (moniteur, Protocole, Manuel, envoi de la sélection).

**Onglet Protocole** (premier onglet)
- Protocole décrit par un fichier JSON (`protocols/`) : rôles, tailles, bits, variantes de trame, codage ASCII, CRC 8/16/32, textes lisibles, catégories.
- Bibliothèque de commandes (`Msg_*.json`, clé `"protocol"` pour filtrer) ; commandes masquées (`"hidden"`, case « Masquées ») ; données prédéfinies.
- Tableau de la trame modifiable sur place : champs de DATA en bleu, colonne **Valeur** (valeur convertie) ou **Hexa** (octets bruts du champ), et ligne **DATA** en hexa brut (les champs montrent alors le décodage). Tableaux Requête et Réponse à la hauteur de leurs lignes, séparateur placé automatiquement.
- REQ+ (REQUEST ID +1 après envoi), Copier, Envoyer, → Replay, **Sauvegarder…** : nom du message (fichier `Msg_<nom>.json` proposé en direct), puis explorateur ; remplacer / garder les deux / annuler si le nom existe.
- Réponse : décodage automatique, codes d'erreur.

**Onglet Manuel**
- Messages des fichiers `msgLibrary/msgManual/Msg_*.json` + fichiers ajoutés (Charger…, sauvegardes hors de `msgLibrary/msgManual/`) **mémorisés** dans settings.json (`message_files`) ; bouton Retirer.
- Doublons : fichier déjà chargé non relu, message identique ignoré, même nom mais contenu différent : les deux gardés, nom du fichier entre crochets.
- Messages « de protocole » (clé `"request"`) : REQUEST ID, COMMAND ID, DATA modifiables, trame construite par le protocole en cours.
- Envoi périodique, envoi d'une sélection avec délai.

**Moniteur, trace, replay** : moniteur TX / RX coloré et décodé, Hexa libre avec CRC auto, timeout de réponse ; trace enregistrée, panneau Replay modifiable, rejeu avec comparaison des réponses.

**Divers** : interface français / anglais ; couleurs réglables ; disposition de la fenêtre mémorisée ; documentation FR (`docs/Francais/`) et EN (`docs/English/`).

## Dernières modifications

- 2026-11-18 : onglet Protocole compacté : ligne « Données » supprimée (données prédéfinies, description, Sauvegarder… et Copier sur la ligne du REQUEST ID ; DATA manuelle dans le tableau), Envoyer et → Replay au bout de la ligne de la trame hexa. Replay : case **Décoder** (ligne cliquée chargée dans la Requête si TX, dans la Réponse si RX, cadre rempli sur fond gris foncé jusqu'au prochain choix de commande), ■ Arrêter grisé hors lecture.
- 2026-11-18 : onglet Protocole : éditeur sous le tableau supprimé (édition directe dans les colonnes Valeur et Hexa du tableau) ; tableaux TX / RX à la hauteur de leurs lignes et séparateur Requête / Réponse placé automatiquement (plus mémorisé) ; trame hexa sur toute la largeur (plusieurs lignes si besoin), boutons en dessous.
- 2026-11-18 : fonctions Modbus standard : `msgLibrary/msgList/modbus/Msg_Modbus_Standard.json` (01 à 06, 07, 08, 0B, 0C, 0F, 10, 11, 14 à 18, 2B / MEI 0E, génériques) et 15 trames Modbus RTU toutes prêtes dans `msgLibrary/msgManual/Msg_Modbus.json` ; une commande précise ("match") et une générique peuvent partager un COMMAND ID (la générique sert de repli au décodage).
- 2026-11-10 : panneau Replay sur fond gris plus foncé ; boutons ⏭ Pas à pas (bleu), ▶ Rejouer (vert), ■ Arrêter (rouge) sous la barre d'édition, avec infobulles ; + Ajouter place la ligne « Délai fixe » ms après celle du dessus ; nom par défaut new_trace_<date>. Moniteur : « Replay » devient « + Replay » (copie les trames du moniteur dans une nouvelle trace), « Exporter… » devient « Sauvegarder… » (trace CSV rejouable ou texte), infobulles.
- 2026-11-10 : replay **pas à pas** : bouton ⏭ Pas à pas / ⏭ Suivant (F8), une requête par clic à partir de la ligne sélectionnée ; résultat au bout du timeout ou au clic suivant.
- 2026-11-10 : dossier `messages/` renommé `msgLibrary/`, séparé en `msgManual/` (messages seuls de l'onglet Manuel, sauvegardes) et `msgList/` (listes de commandes des protocoles, sous-dossiers `modbus/`, `mbus/`, `profibus/`).

## À faire / idées

- Garder `docs/English/` synchronisé à chaque modification de `docs/Francais/`.
