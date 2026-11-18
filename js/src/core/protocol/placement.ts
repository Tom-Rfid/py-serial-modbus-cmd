/**
 * core/protocol/placement.ts — Ordre final des champs (portage de core/protocol/placement.py).
 *
 *   "at": 6        commence à l'octet 6 (les trous deviennent des octets non lus)
 *   "at": "start"  en tête ; "at": "end" : en fin de trame
 *   "after": "NOM" juste après le champ NOM (en cascade)
 *
 * 1. ordre logique : "start", puis les champs sans placement (chacun suivi de ses "after") ;
 * 2. champs à octet fixe insérés à leur position (prioritaires), les autres s'écoulent autour ;
 * 3. les champs "end" ferment la trame.
 */
import { ProtocolError } from './common';
import { atText, positionText, type FieldSpec } from './fields';

export function orderFields(fields: FieldSpec[], kind: string): FieldSpec[] {
  const names = new Set(fields.map((f) => f.name));
  for (const f of fields) {
    if (f.after !== undefined && !names.has(f.after)) {
      throw new ProtocolError(`${kind} : champ '${f.name}' : after désigne un champ inconnu '${f.after}'`);
    }
  }
  const followers = followersOf(fields);
  const placed = new Set<string>();
  const sequence = [
    ...group(fields, (f) => f.at === 'start', followers, placed),
    ...group(fields, (f) => f.at === undefined && f.after === undefined, followers, placed),
  ];
  const numeric = fields.filter((f) => typeof f.at === 'number').sort((a, b) => (a.at as number) - (b.at as number));
  const blocks = numeric.map((f) => block(f, followers, placed));
  const tail = group(fields, (f) => f.at === 'end', followers, placed);
  checkAllPlaced(fields, placed, kind);
  return [...insertAtBytes(sequence, blocks, kind), ...tail];
}

function followersOf(fields: FieldSpec[]): Map<string, FieldSpec[]> {
  const out = new Map<string, FieldSpec[]>();
  for (const f of fields) {
    if (f.after === undefined) continue;
    if (!out.has(f.after)) out.set(f.after, []);
    out.get(f.after)!.push(f);
  }
  return out;
}

/** Le champ f suivi de ses champs "after", en cascade. */
function block(f: FieldSpec, followers: Map<string, FieldSpec[]>, placed: Set<string>): FieldSpec[] {
  const out = [f];
  placed.add(f.name);
  for (const g of followers.get(f.name) ?? []) {
    if (!placed.has(g.name)) out.push(...block(g, followers, placed));
  }
  return out;
}

function group(fields: FieldSpec[], keep: (f: FieldSpec) => boolean, followers: Map<string, FieldSpec[]>, placed: Set<string>): FieldSpec[] {
  const out: FieldSpec[] = [];
  for (const f of fields) if (keep(f) && !placed.has(f.name)) out.push(...block(f, followers, placed));
  return out;
}

function checkAllPlaced(fields: FieldSpec[], placed: Set<string>, kind: string): void {
  const missing = fields.filter((f) => !placed.has(f.name)).map((f) => f.name);
  if (missing.length) throw new ProtocolError(`${kind} : placement circulaire (after) : ${missing.join(', ')}`);
}

function insertAtBytes(sequence: FieldSpec[], blocks: FieldSpec[][], kind: string): FieldSpec[] {
  const result: FieldSpec[] = [];
  const queue = [...sequence];
  let offset = 0;
  let lastVariable: string | undefined;
  for (const b of blocks) {
    const head = b[0];
    const at = head.at as number;
    if (lastVariable !== undefined) {
      throw new ProtocolError(`${kind} : champ '${head.name}' : impossible de le placer ${atText(at)}, le champ '${lastVariable}' qui le précède n'a pas une taille fixe`);
    }
    offset = flowUntil(result, queue, offset, at);
    if (offset > at) {
      throw new ProtocolError(`${kind} : champ '${head.name}' : ${positionText(at)} est déjà occupé (les champs précédents vont jusqu'${endText(offset)})`);
    }
    if (offset < at) {
      result.push(gap(offset, at - offset));
      offset = at;
    }
    for (const f of b) {
      result.push(f);
      if (fixedSize(f)) offset += f.bits!;
      else lastVariable = f.name;
    }
  }
  return [...result, ...queue];
}

/** Place les champs sans position fixe qui tiennent entièrement avant l'octet `at`. */
function flowUntil(result: FieldSpec[], queue: FieldSpec[], offset: number, at: number): number {
  while (queue.length) {
    const f = queue[0];
    if (!fixedSize(f) || offset + f.bits! > at) break;
    result.push(queue.shift()!);
    offset += f.bits!;
  }
  return offset;
}

/** Taille connue au chargement : ni DATA variable, ni champ conditionnel ("if"). */
function fixedSize(f: FieldSpec): boolean {
  return f.bits !== undefined && !(f.cond && f.bits);
}

/** « à l'octet 3 » / « au bit 19 » : dernière position occupée avant `offset` (en bits). */
function endText(offset: number): string {
  return offset % 8 === 0 ? `à l'octet ${offset / 8 - 1}` : `au bit ${offset - 1}`;
}

/** Bits non couverts : champ non lu (rôle na) créé automatiquement, nommé en octets ou en bits. */
function gap(start: number, bits: number): FieldSpec {
  let name: string;
  if (start % 8 === 0 && bits % 8 === 0) {
    const first = start / 8;
    const last = (start + bits) / 8 - 1;
    name = first === last ? `(octet ${first})` : `(octets ${first}-${last})`;
  } else {
    const last = start + bits - 1;
    name = start === last ? `(bit ${start})` : `(bits ${start}-${last})`;
  }
  return { name, role: 'na', bits, default: 0, fill: 0, color: 'na', over: [0, 'end'], of: [], description: '', descriptionEn: '' };
}
