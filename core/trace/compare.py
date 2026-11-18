"""
core/trace/compare.py — Comparaison des réponses rejouées aux réponses enregistrées, avec timeout.
"""
from ..frames import to_hex


def compare(expected, actual):
    """Compare deux trames. Retourne (identiques, explication).

    Ex. (False, "octets 7-8 : attendu 12 34, reçu 12 35")
        (False, "longueur : attendu 11, reçu 9 ; octet 2 : attendu 00, reçu 04")
    """
    if expected == actual:
        return True, "identique"
    parts = []
    if len(expected) != len(actual):
        parts.append(f"longueur : attendu {len(expected)}, reçu {len(actual)}")
    # Plages d'octets différents (sur la longueur commune)
    diffs = [i for i in range(min(len(expected), len(actual))) if expected[i] != actual[i]]
    ranges = []
    for i in diffs:
        if ranges and i == ranges[-1][1] + 1:
            ranges[-1][1] = i
        else:
            ranges.append([i, i])
    for a, b in ranges[:4]:
        where = f"octet {a}" if a == b else f"octets {a}-{b}"
        parts.append(f"{where} : attendu {to_hex(expected[a:b + 1])}, reçu {to_hex(actual[a:b + 1])}")
    if len(ranges) > 4:
        parts.append(f"… {len(ranges) - 4} autre(s) écart(s)")
    return False, " ; ".join(parts)


def compare_responses(expected, actual):
    """Compare les réponses enregistrées et reçues d'un échange.

    expected, actual : listes d'octets (une entrée par trame).
    Retourne (statut, explication), statut parmi :
        "identique", "différent", "sans réponse", "réponse en trop", "aucune attendue"
    """
    if not expected and not actual:
        return "aucune attendue", ""
    if not actual:
        return "sans réponse", f"{len(expected)} trame(s) attendue(s)"
    if not expected:
        return "réponse en trop", f"{len(actual)} trame(s) reçue(s), aucune enregistrée"
    notes = []
    same = len(expected) == len(actual)
    for i, (e, a) in enumerate(zip(expected, actual)):
        ok, why = compare(e, a)
        if not ok:
            same = False
            notes.append((f"trame {i + 1} : " if len(expected) > 1 else "") + why)
    if len(expected) != len(actual):
        notes.append(f"{len(expected)} trame(s) attendue(s), {len(actual)} reçue(s)")
    return ("identique", "") if same else ("différent", " ; ".join(notes))


DEFAULT_TIMEOUT_MS = 500


def judge_exchange(expected, received, timeout_ms=DEFAULT_TIMEOUT_MS):
    """Verdict d'un échange rejoué, en tenant compte du timeout de réponse.

    expected  : réponses enregistrées dans la trace (liste d'octets)
    received  : réponses reçues au replay, [(latence_ms, octets)] dans l'ordre d'arrivée
    timeout_ms: délai maximal entre l'envoi et une réponse ; une réponse plus
                tardive ne compte pas

    Retourne (statut, explication), statut parmi :
        "identique"       mêmes octets, reçus à temps
        "différent"       reçus à temps mais octets différents (explication : octets en cause)
        "timeout"         réponse attendue, rien reçu dans le délai (explication : réponse tardive éventuelle)
        "réponse en trop" rien d'attendu, mais une réponse est arrivée
        "aucune attendue" rien d'attendu, rien reçu
    """
    on_time = [data for lat, data in received if lat <= timeout_ms]
    late = [lat for lat, _ in received if lat > timeout_ms]
    if expected and not on_time:
        why = f"aucune réponse en {timeout_ms:.0f} ms"
        if late:
            why += f" (réponse arrivée après {late[0]:.0f} ms)"
        return "timeout", why
    status, why = compare_responses(expected, on_time)
    if late and status in ("identique", "différent"):
        why = (why + " ; " if why else "") + f"{len(late)} trame(s) après le timeout ignorée(s)"
    return status, why
