"""
core/protocol/placement.py — Ordre final des champs d'une trame.

Par défaut les champs se suivent dans l'ordre de la liste "tx" / "rx". Chaque champ
peut aussi dire où il se place :

    "at": 6           commence à l'octet 6 (aussi "atO") ; "atb": 13 : commence au bit 13
                      (les trous éventuels deviennent des octets / bits non lus)
    "at": "start"     en tête de trame
    "at": "end"       en fin de trame (ex. un CRC final), dans l'ordre de la liste s'il y en a plusieurs
    "after": "NOM"    juste après le champ NOM (et ce qui le suit en cascade)

Étapes :
    1. ordre logique : "start", puis les champs sans placement (chacun suivi de ses
       champs "after") ; les champs "end" sont mis de côté pour la fin
    2. les champs à octet fixe ("at": entier) sont insérés à leur position, prioritaires ;
       les autres s'écoulent autour : avant s'ils tiennent entièrement, sinon après.
       Un trou devient un champ non lu (rôle na)
    3. les champs "end" (et leurs champs "after") ferment la trame
"""
from .common import ProtocolError
from .fields import FieldSpec, at_text, position_text


def order_fields(fields, kind):
    """Liste des champs dans l'ordre des octets de la trame. Lève ProtocolError si le placement est impossible."""
    names = {f.name for f in fields}
    for f in fields:
        if f.after is not None and f.after not in names:
            raise ProtocolError(f"{kind} : champ {f.name!r} : after désigne un champ inconnu '{f.after}'")
    followers = _followers(fields)
    placed = set()
    sequence = _group(fields, lambda f: f.at == "start", followers, placed) + \
        _group(fields, lambda f: f.at is None and f.after is None, followers, placed)
    numeric = sorted((f for f in fields if isinstance(f.at, int)), key=lambda f: f.at)
    blocks = [_block(f, followers, placed) for f in numeric]
    tail = _group(fields, lambda f: f.at == "end", followers, placed)
    _check_all_placed(fields, placed, kind)
    # Les champs "end" restent en fin de trame, après tout le reste
    return _insert_at_bytes(sequence, blocks, kind) + tail


def _followers(fields):
    """{nom: [champs placés juste après lui]}, dans l'ordre de la liste."""
    out = {}
    for f in fields:
        if f.after is not None:
            out.setdefault(f.after, []).append(f)
    return out


def _block(f, followers, placed):
    """Le champ f suivi de ses champs "after", en cascade."""
    block = [f]
    placed.add(f.name)
    for g in followers.get(f.name, []):
        if g.name not in placed:
            block.extend(_block(g, followers, placed))
    return block


def _group(fields, keep, followers, placed):
    """Les champs retenus par keep(), chacun suivi de ses champs "after"."""
    out = []
    for f in fields:
        if keep(f) and f.name not in placed:
            out.extend(_block(f, followers, placed))
    return out


def _check_all_placed(fields, placed, kind):
    """Un champ jamais placé appartient à une boucle de "after" (A après B, B après A)."""
    missing = [f.name for f in fields if f.name not in placed]
    if missing:
        raise ProtocolError(f"{kind} : placement circulaire (after) : {', '.join(missing)}")


def _insert_at_bytes(sequence, blocks, kind):
    """Insère les blocs à position fixe ; les autres champs s'écoulent autour (avant s'ils tiennent,
    sinon après). Les positions fixes sont prioritaires. Tout est compté en bits."""
    result, queue, offset, last_variable = [], list(sequence), 0, None
    for block in blocks:
        head = block[0]
        if last_variable is not None:
            raise ProtocolError(f"{kind} : champ {head.name!r} : impossible de le placer {at_text(head.at)}, "
                                f"le champ {last_variable!r} qui le précède n'a pas une taille fixe")
        offset = _flow_until(result, queue, offset, head)
        if offset > head.at:
            raise ProtocolError(f"{kind} : champ {head.name!r} : {position_text(head.at)} est déjà occupé "
                                f"(les champs précédents vont jusqu'{_end_text(offset)})")
        if offset < head.at:
            result.append(_gap(offset, head.at - offset))
            offset = head.at
        for f in block:
            result.append(f)
            if _fixed_size(f):
                offset += f.bits
            else:
                last_variable = f.name
    return result + queue


def _end_text(offset):
    """« à l'octet 3 » / « au bit 19 » : dernière position occupée avant `offset` (en bits)."""
    if offset % 8 == 0:
        return f"à l'octet {offset // 8 - 1}"
    return f"au bit {offset - 1}"


def _flow_until(result, queue, offset, head):
    """Place les champs sans position fixe qui tiennent entièrement avant la position head.at.

    S'arrête au premier champ qui dépasserait, ou dont la taille n'est pas fixe : il
    sera placé après le bloc.
    """
    while queue:
        f = queue[0]
        if not _fixed_size(f) or offset + f.bits > head.at:
            break
        result.append(queue.pop(0))
        offset += f.bits
    return offset


def _fixed_size(f):
    """Taille connue au chargement : ni DATA variable, ni champ conditionnel ("if")."""
    return f.bits is not None and not (f.cond and f.bits)


def _gap(start, bits):
    """Bits non couverts par un champ : champ non lu (rôle na) créé automatiquement.

    Nommé en octets s'il tombe sur des octets entiers ("(octets 2-3)"), sinon en bits ("(bits 12-15)").
    """
    if start % 8 == 0 and bits % 8 == 0:
        first, last = start // 8, (start + bits) // 8 - 1
        name = f"(octet {first})" if first == last else f"(octets {first}-{last})"
    else:
        first, last = start, start + bits - 1
        name = f"(bit {first})" if first == last else f"(bits {first}-{last})"
    return FieldSpec(name, "na", bits=bits, color="na")
