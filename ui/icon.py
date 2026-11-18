"""
ui/icon.py — Icône de la fenêtre (barre de titre en haut à gauche, barre des tâches, Alt+Tab).

L'icône est un fichier PNG désigné par edition.json ("icon", par défaut assets/icon.png) :
pour la changer, il suffit de remplacer ce fichier (256 × 256 conseillé, fond transparent).
Sous Windows, le fichier .ico du même nom (assets/icon.ico, plusieurs tailles) est utilisé en
plus : c'est la seule façon fiable d'avoir l'icône dans la barre de titre et la barre des tâches.
Fichier absent ou illisible : icône par défaut de Tk, sans message d'erreur.
"""
import sys
import tkinter as tk
from pathlib import Path


def set_windows_app_id(app_id):
    """Windows : identifiant d'application propre à SerialHex.

    Sans lui, Windows regroupe la fenêtre avec python.exe et affiche l'icône de Python dans la
    barre des tâches. À appeler AVANT de créer la fenêtre. Sans effet hors Windows."""
    if sys.platform != "win32":
        return
    try:
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(str(app_id))
    except (AttributeError, OSError):
        pass


def set_window_icon(window, path):
    """Applique l'image PNG `path` comme icône de `window` (et des fenêtres filles).

    Retourne l'image Tk (ou None si le PNG est absent / illisible)."""
    path = Path(path)
    image = _load_png(path)
    if image is not None:
        # Plusieurs tailles : le système prend la plus proche (16 px barre de titre, 32 px Alt+Tab…)
        sizes = [image] + [image.subsample(f) for f in (2, 4, 8, 16) if image.width() // f >= 16]
        window.iconphoto(True, *sizes)
        window._icon_images = sizes     # garder une référence, sinon Tk efface les images
    if sys.platform == "win32":
        _set_windows_ico(window, path.with_suffix(".ico"))
    return image


def _load_png(path):
    try:
        return tk.PhotoImage(file=str(path))
    except (tk.TclError, OSError):
        return None


def _set_windows_ico(window, ico):
    """Windows : icône .ico (barre de titre et barre des tâches), pour cette fenêtre et les suivantes."""
    if not ico.is_file():
        return
    try:
        window.iconbitmap(default=str(ico))
    except tk.TclError:
        pass
