"""
core/commands/describe.py — Résumé d'une ligne d'une trame décodée, enrichi par la bibliothèque
(journal du moniteur).

    describe(d, cmd, lib)        -> « réponse #0x05 · Lire l'état · erreur 0 (OK) · 1 o · CRC OK »
    describe_parts(d, cmd, lib)  -> le même résumé en morceaux [(texte, ok)] : ok = False pour
                                    ce qui doit ressortir en rouge (code d'erreur non nul, CRC faux…)
"""
from ..protocol import request_id_text, status_parts


def describe(decoded, command=None, library=None):
    """Résumé d'une trame décodée.

    Ex. « réponse #0x05 · Lire l'état · erreur 0 (OK) · 1 o · CRC OK »
    Fonctionne avec tout protocole décrit par fichier de conf (champs repérés par leur rôle).
    """
    return " · ".join(text for text, _ in describe_parts(decoded, command, library))


def describe_parts(decoded, command=None, library=None):
    """Morceaux du résumé : [(texte, ok)].

    Ex. réponse en erreur :
        [("réponse #0x06", True), ("Lire l'état", True),
         ("erreur 1 (Commande inconnue)", False), ("0 o", True), ("CRC OK", True)]
    Seul le texte de l'erreur est en rouge : les octets de la réponse (en-tête compris)
    sont corrects, c'est la requête que l'appareil a refusée.
    """
    parts = [(decoded.kind + request_id_text(decoded), True)]
    name = _command_text(decoded, command)
    if name:
        parts.append((name, True))
    if decoded.error is not None:
        parts.append((_error_text(decoded.error, library), decoded.error == 0))
    parts.extend(status_parts(decoded))
    return parts


def _command_text(decoded, command):
    """Nom de la commande de la bibliothèque, sinon son COMMAND ID en hexa, sinon ''."""
    if command:
        return command.name
    cid = decoded.by_role("command_id")
    if cid is not None:
        return f"cmd 0x{cid.value:0{cid.hex_digits}X}"
    return ""


def _error_text(code, library):
    text = library.error_text(code) if library else ""
    return f"erreur {code}" + (f" ({text})" if text else "")
