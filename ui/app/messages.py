"""
ui/app/messages.py — Messages JSON de l'onglet Manuel : chargement et sélection.

L'onglet Manuel ne montre que les messages des fichiers Msg_*.json (clé "messages") du dossier
msgLibrary/msgManual/ et des fichiers ajoutés (« Charger… », sauvegardes hors de msgLibrary/msgManual/), dont la liste
est mémorisée dans settings.json ("message_files") : des trames toutes prêtes.
Les commandes du protocole, elles, sont dans l'onglet Protocole.
"""
from pathlib import Path
from tkinter import filedialog, messagebox

from core.frames import defaults_for
from core.messages import MSG_PREFIX, load_folder, load_messages, merge_messages, message_files, message_key
from core.request_message import SAVED_FILE, find_saved, save_message_file, saved_file_name, unique_name
from ui.i18n import _, tr


class MessagesMixin:
    def _set_messages(self, messages):
        """Remplace la liste des messages (les valeurs saisies sont oubliées)."""
        self.messages = messages
        self.values = {}
        self.params.clear()
        self.messages_panel.set_messages(messages)

    def reload_messages(self):
        """Bouton Recharger (et lancement) : relit les Msg_*.json de msgLibrary/msgManual/, les fichiers
        ajoutés (Charger…, sauvegardes hors de msgLibrary/msgManual/, mémorisés dans settings.json),
        le fichier de protocole et la bibliothèque de commandes."""
        self.extra_files = [Path(p) for p in self.settings.get("message_files") or []]
        messages = self._reload_all()
        n_extra = len(self.extra_files)
        if messages:
            text = _("{0} message(s) chargé(s) depuis {1}/").format(len(messages), self.messages_dir.name)
            if n_extra:
                text += _(" et {0} fichier(s) ajouté(s)").format(n_extra)
            self.monitor.log(text, "INFO")
        elif message_files(self.messages_dir):
            # Des Msg_*.json, mais seulement des commandes du protocole (onglet Protocole)
            self.monitor.log(_("Pas de message pour l'onglet Manuel dans {0}/ (commandes du protocole seulement)")
                             .format(self.messages_dir.name), "INFO")
        else:
            self.monitor.log(_("Aucun fichier {0}*.json dans {1}").format(MSG_PREFIX, self.messages_dir), "INFO")
        self.load_protocol(self.protocol_file())
        self.load_library()

    def _folder_files(self):
        """Fichiers de messages du dossier msgLibrary/msgManual/ (chemins absolus)."""
        return {p.resolve() for p in message_files(self.messages_dir)}

    def _remember_files(self):
        """Liste des fichiers ajoutés mémorisée tout de suite dans settings.json."""
        self.settings["message_files"] = [str(p) for p in self.extra_files]
        self.settings.save()

    def load_files(self, paths):
        """Bouton Charger… : ajoute les messages de fichiers choisis à la main (mémorisés :
        ils restent dans la liste après une sauvegarde, Recharger ou au lancement suivant).

        Un fichier déjà chargé (dossier msgLibrary/msgManual/ ou Charger…) n'est pas relu ; un message
        identique à un message déjà présent est ignoré ; deux messages de même nom (et même
        groupe) mais différents sont gardés, le nom du fichier d'origine les distingue."""
        messages = list(self.messages)
        loaded = self._folder_files() | set(self.extra_files)
        for path in paths:
            path = Path(path).resolve()
            if path in loaded:
                self.monitor.log(_("{0} déjà chargé : ignoré").format(path.name), "INFO")
                continue
            try:
                found = load_messages(path)
            except Exception as e:
                self.monitor.log(f"{path.name} : {e}", "ERR")
                continue
            loaded.add(path)
            self.extra_files.append(path)
            messages, added, same = merge_messages(messages, found)
            text = _("{0} message(s) ajouté(s) depuis {1}").format(added, path.name)
            if same:
                text += _(" ; {0} message(s) identique(s) déjà présent(s), ignoré(s)").format(same)
            self.monitor.log(text, "INFO")
        self._remember_files()
        self._set_messages(messages)

    def remove_files(self, ids):
        """Bouton Retirer : les fichiers ajoutés d'où viennent les messages sélectionnés
        quittent la liste (rien n'est effacé du disque). Les fichiers de msgLibrary/msgManual/ restent."""
        paths = {Path(self.messages[i]["_path"]) for i in ids if self.messages[i].get("_path")}
        removed = [p for p in self.extra_files if p in paths]
        if not removed:
            self.monitor.log(_("Fichier du dossier {0}/ : toujours affiché (Retirer ne concerne que les fichiers ajoutés)")
                             .format(self.messages_dir.name), "INFO")
            return
        self.extra_files = [p for p in self.extra_files if p not in paths]
        self._remember_files()
        self._reload_all()
        for p in removed:
            self.monitor.log(_("{0} retiré de la liste").format(p.name), "INFO")

    def _reload_all(self):
        """Dossier msgLibrary/msgManual/ puis fichiers ajoutés (Charger…, sauvegardes hors de msgLibrary/msgManual/)."""
        messages, errors = load_folder(self.messages_dir)
        folder = self._folder_files()
        kept = []
        for path in self.extra_files:
            path = Path(path).resolve()
            if path in folder or path in kept:
                continue
            if not path.is_file():
                self.monitor.log(_("{0} introuvable : retiré de la liste").format(path), "ERR")
                continue
            kept.append(path)
            try:
                messages, _added, _same = merge_messages(messages, load_messages(path))
            except Exception as e:
                errors.append((path.name, str(e)))
        if kept != self.extra_files:
            self.extra_files = kept
            self._remember_files()
        self._set_messages(messages)
        for name, err in errors:
            self.monitor.log(_("{0} ignoré : {1}").format(name, tr(str(err))), "ERR")
        return messages

    def ask_save_path(self, initial=SAVED_FILE):
        """Explorateur « Enregistrer sous » : fichier de messages où sauvegarder ("" = annulé).
        initial : fichier proposé (Msg_<nom du message>.json), modifiable."""
        return filedialog.asksaveasfilename(
            parent=self, title=_("Sauvegarder le message dans…"), initialdir=str(self.messages_dir),
            initialfile=initial, defaultextension=".json", confirmoverwrite=False,
            filetypes=[(_("Messages"), "Msg_*.json"), ("JSON", "*.json")])

    def ask_duplicate(self, name, file_name):
        """Nom déjà pris dans le fichier : True = remplacer, False = garder les deux, None = annuler."""
        return messagebox.askyesnocancel(
            _("Message déjà présent"),
            _("Le message « {0} » existe déjà dans {1}.\n\nOui : le remplacer\n"
              "Non : garder les deux (le nouveau devient « {2} »)\nAnnuler : ne rien sauvegarder")
            .format(name, file_name, unique_name(self._save_target, name)), parent=self)

    def save_message(self, msg, file_name=SAVED_FILE):
        """Bouton « Sauvegarder… » de l'onglet Protocole : fichier choisi dans l'explorateur
        (msgLibrary/msgManual/<file_name> proposé, Msg_<nom>.json ; préfixe Msg_ ajouté au besoin), puis liste de
        l'onglet Manuel relue (le message y est sélectionné). Nom déjà pris dans le fichier :
        message identique = rien à faire ; sinon remplacer, garder les deux ou annuler."""
        chosen = self.ask_save_path(file_name)
        if not chosen:
            return
        path = Path(chosen)
        path = path.with_name(saved_file_name(path.name)).resolve()
        self._save_target = path
        existing = find_saved(path, msg["name"])
        if existing is not None and message_key(existing) == message_key(msg):
            self.monitor.log(_("Message « {0} » déjà présent, identique, dans {1}").format(msg["name"], path.name), "INFO")
        else:
            if existing is not None:
                answer = self.ask_duplicate(msg["name"], path.name)
                if answer is None:
                    return
                if answer is False:
                    msg = dict(msg, name=unique_name(path, msg["name"]))
            try:
                path, replaced = save_message_file(path, msg)
            except (OSError, ValueError) as e:
                self.monitor.log(_("Sauvegarde impossible : {0}").format(e), "ERR")
                return
            text = _("Message « {0} » remplacé dans {1}") if replaced else _("Message « {0} » sauvegardé dans {1}")
            self.monitor.log(text.format(msg["name"], path.name), "INFO")
        if path not in self._folder_files() and path not in self.extra_files:
            self.extra_files.append(path)         # hors de msgLibrary/msgManual/ : chargé quand même (mémorisé)
            self._remember_files()
        messages = self._reload_all()
        key = message_key(msg)
        idx = next((i for i, m in enumerate(messages) if message_key(m) == key), None)
        if idx is not None:
            self.messages_panel.select(idx)

    def values_for(self, idx):
        """Valeurs du message idx ; créées avec les valeurs par défaut au premier accès."""
        if idx not in self.values:
            self.values[idx] = defaults_for(self.messages[idx])
        return self.values[idx]

    def select_message(self, idx):
        """Un message est sélectionné dans la liste : on affiche ses paramètres."""
        self.params.show(idx, self.messages[idx], self.values_for(idx), current_protocol=self.proto.name)
