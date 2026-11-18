"""
core/protocol/common.py — Constantes et outils partagés par le moteur de protocole.
"""

QUERY = "requête"       # trame envoyée à l'appareil (clé "tx" du fichier de conf)
RESPONSE = "réponse"    # trame reçue de l'appareil (clé "rx")
KIND_KEYS = {QUERY: "tx", RESPONSE: "rx"}


class ProtocolError(ValueError):
    """Fichier de configuration de protocole invalide (message lisible)."""


def to_int(value, what):
    """Entier lu dans le JSON : nombre, ou texte décimal / "0x..." / "0b...".

    what : nom de la clé, pour le message d'erreur.
    """
    if isinstance(value, bool) or value is None:
        raise ProtocolError(f"{what} : entier attendu")
    if isinstance(value, int):
        return value
    try:
        return int(str(value).strip(), 0)
    except ValueError:
        raise ProtocolError(f"{what} : entier attendu, pas '{value}'") from None
