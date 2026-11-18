"""
ui/hexview.py — Affichage d'une trame hexa en couleurs.

Code couleur commun à l'onglet Manuel, à l'onglet Protocole et au moniteur
(pour le protocole, chaque champ choisit sa couleur dans protocols/<nom>.json) :
    hdr : en-tête        gris clair   (octets fixes d'un message ; synchro, adresse, numéro de requête)
    cmd : COMMAND ID     gras
    crc : checksum / CRC vert pastel
    na  : octets non lus  gris très clair, barré
    err : CRC faux                           rouge, gras
    perr_ok / perr_ko : code d'erreur        fond vert si 0 (pas d'erreur), fond rouge sinon
                        (fond coloré : bien visible sur les lignes TX bleues et RX violettes)
    val : valeur convertie (moniteur)        gras, couleur de la ligne (TX bleu, RX violet)
    data : DATA (aperçus des onglets)         bleu (couleur des trames TX)

Contenu
    - message_segments()  : morceaux colorés d'un message JSON (onglet Manuel)
    - protocol_segments() : morceaux colorés d'une trame du protocole en cours
    - hex_chunks()        : texte hexa découpé en morceaux (texte, tags) pour un tk.Text
    - configure_tags()    : déclare les couleurs dans un tk.Text
    - HexView             : petite zone de texte qui affiche une trame colorée

Un « segment » est un triplet (premier octet, nombre d'octets, tag).
"""
import tkinter as tk

from core.frames import to_hex
from core.protocol import color_segments
from ui.theme import THEME, ensure_hex_tag, readable_on

# Morceaux d'un message JSON (core.frames.frame_segments) -> tag
MESSAGE_TAGS = {"fixed": "hdr", "cs": "crc"}


def message_segments(frame_segs):
    """[(nature, octets)] de frame_segments -> [(début, longueur, tag)]."""
    out, pos = [], 0
    for kind, data in frame_segs:
        tag = MESSAGE_TAGS.get(kind)
        if tag and data:
            out.append((pos, len(data), tag))
        pos += len(data)
    return out


def protocol_segments(decoded, protocol=None, data=False):
    """Trame du protocole décodée (core.protocol.Decoded) -> [(début, longueur, tag)].

    Couleur de chaque champ : celle du fichier de conf du protocole ("color" :
    hdr, cmd, crc). Les couleurs ne sont appliquées que si la trame est COMPLÈTE :
    une trame en cours de saisie ou tronquée reste sans couleur. Un octet fixe
    ou un CRC incorrect est en rouge ; le code d'erreur (rôle error) est sur fond
    vert à 0 (pas d'erreur), rouge sinon.
    data=True : octets de DATA en bleu (aperçus des onglets Manuel et Protocole ; dans le
    moniteur, DATA garde la couleur de la ligne).
    """
    segments = color_segments(decoded)
    d = decoded.data
    if data and decoded.complete and d is not None and d.raw:
        segments = [(d.start, len(d.raw), "data")] + list(segments)     # les autres couleurs l'emportent
    # Codage ASCII (Modbus ASCII) : les couleurs suivent les caractères envoyés
    return protocol.display_segments(decoded, segments) if protocol is not None else segments


def hex_chunks(data, segments=None, base_tags=()):
    """Texte hexa de `data` découpé en morceaux [(texte, tags)] selon les segments.

    base_tags : tags appliqués à tout le texte (ex. ("RX",) pour la couleur de la ligne).
    Les octets consécutifs de même tag sont regroupés ; les espaces entre deux
    morceaux prennent les tags de base.
    """
    tag_of = [None] * len(data)
    for start, length, tag in segments or ():
        for i in range(start, min(start + length, len(data))):
            tag_of[i] = tag
    chunks = []
    i = 0
    while i < len(data):
        j = i
        while j < len(data) and tag_of[j] == tag_of[i]:
            j += 1
        tags = tuple(base_tags) + ((tag_of[i],) if tag_of[i] else ())
        if chunks:
            chunks.append((" ", tuple(base_tags)))
        chunks.append((to_hex(data[i:j]), tags))
        i = j
    return chunks


def configure_tags(text, font):
    """Déclare les tags de couleur dans un tk.Text, avec les couleurs de ui/theme.py.

    À appeler APRÈS les tags de couleur de ligne (TX, RX...) : un tag déclaré
    plus tard est prioritaire, donc l'en-tête et le CRC gardent leur couleur.
    font : police de base (le tag « cmd » en est la version grasse).
    Les couleurs suivent la page « Couleurs… » (abonnement au thème).
    """
    THEME.subscribe(lambda: apply_field_colors(text, font))


def apply_field_colors(text, font, colors=None):
    """(Re)configure les tags des champs avec `colors` (par défaut celles du thème)."""
    c = colors or THEME.colors
    bold = (font[0], font[1], "bold")
    text.tag_configure("hdr", foreground=c["hdr"])
    text.tag_configure("crc", foreground=c["crc"])
    text.tag_configure("na", foreground=c["na"], overstrike=True)
    text.tag_configure("cmd", font=bold, foreground=c["cmd"])        # "" : couleur de la ligne
    text.tag_configure("err", foreground=c["err"], font=bold)
    for tag in ("perr_ok", "perr_ko"):
        text.tag_configure(tag, background=c[tag], foreground=readable_on(c[tag]), font=bold)
    text.tag_configure("val", font=bold)                              # valeurs converties (moniteur)
    text.tag_configure("data", foreground=c["tx"])                    # DATA des aperçus


class HexView(tk.Text):
    """Zone de texte en lecture seule qui affiche une trame colorée, suivie d'un commentaire.

        view.show(data, segments, suffix="   (8 octets)")
        view.show_error("Erreur : ...")

    max_lines : si donné, la hauteur suit le texte affiché (de `height` à max_lines lignes),
                pour qu'une longue trame se voie en entier ; None = hauteur fixe.
    """

    def __init__(self, master, font=("Consolas", 11), height=1, max_lines=None, **kw):
        bg = master.winfo_toplevel().cget("background")
        super().__init__(master, height=height, font=font, wrap="word", borderwidth=0,
                         highlightthickness=0, background=bg, cursor="arrow", **kw)
        configure_tags(self, font)
        self.configure(state="disabled")
        self._min_lines, self._max_lines = height, max_lines
        if max_lines:
            # Largeur changée (fenêtre redimensionnée) : le nombre de lignes peut changer
            self.bind("<Configure>", lambda e: self._fit_lines(), add="+")

    def _set(self, chunks):
        self.configure(state="normal")
        self.delete("1.0", "end")
        for text, tags in chunks:
            for tag in tags:
                ensure_hex_tag(self, tag)       # couleur "#RRGGBB" du fichier de protocole
            self.insert("end", text, tags)
        self.configure(state="disabled")
        if self._max_lines:
            self.after_idle(self._fit_lines)    # le compte des lignes affichées demande la géométrie

    def _fit_lines(self):
        """Hauteur = nombre de lignes affichées (retour à la ligne compris), entre les bornes."""
        try:
            lines = self.count("1.0", "end-1c", "displaylines")
        except tk.TclError:                     # widget détruit entre-temps
            return
        lines = (lines[0] if isinstance(lines, tuple) else lines) or 0
        wanted = max(self._min_lines, min(self._max_lines, lines + 1))
        if int(self.cget("height")) != wanted:
            self.configure(height=wanted)

    def show(self, data, segments=None, suffix=""):
        chunks = hex_chunks(data, segments)
        if suffix:
            chunks.append((suffix, ()))
        self._set(chunks)

    def show_error(self, text):
        self._set([(text, ("err",))])

    def clear(self):
        self._set([])
