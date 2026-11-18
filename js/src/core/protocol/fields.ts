/**
 * core/protocol/fields.ts — Description d'un champ de trame (portage de core/protocol/fields.py).
 *
 * Rôles : value (octets fixes vérifiés), request_id, command_id, length ("of"),
 * error, crc ("algo", "over"), data, field ("default"), na (octets non lus, "fill").
 * Taille : "size" / "LENO" en octets, "LENb" en bits. Placement : "at" / "atO" (octet,
 * "start", "end"), "atb" (bit) ou "after" (voir placement.ts). En interne : des BITS.
 * Couleur : hdr, cmd, crc, na, ou directement "#RRGGBB".
 */
import { ProtocolError, toInt, type ByteOrder } from './common';
import { CRC_PRESETS, type Crc } from './crc';

export const ROLES = ['value', 'request_id', 'command_id', 'length', 'error', 'crc', 'data', 'field', 'na', 'copy'] as const;
export type FieldRole = (typeof ROLES)[number];
const UNIQUE_ROLES: FieldRole[] = ['request_id', 'command_id', 'length', 'error', 'data'];
const NUMERIC_ROLES: FieldRole[] = ['value', 'request_id', 'command_id', 'length', 'error', 'field', 'copy'];

/** Texte d'une valeur : chaîne, ou {fr, en} selon la langue. */
export type ValueText = string | { fr?: string; en?: string };
export type FieldColor = 'hdr' | 'cmd' | 'crc' | 'na' | `#${string}`;
const COLORS = ['hdr', 'cmd', 'crc', 'na'];
const HEX_COLOR = /^#[0-9A-Fa-f]{6}$/;
const PLACES = ['start', 'end'];
const MAX_BYTES: Partial<Record<FieldRole, number>> = { data: 0xffff, na: 255 };
const BYTE_SIZE_KEYS = ['size', 'LENO', 'LEN0'];
const BIT_SIZE_KEYS = ['LENb'];
const BYTE_AT_KEYS = ['at', 'atO', 'at0'];
const BIT_AT_KEYS = ['atb'];
const WHOLE_BYTES: FieldRole[] = ['data', 'crc'];

export type Pos = number | string;

export interface FieldSpec {
  name: string;
  role: FieldRole;
  /** Taille en bits ; undefined = variable (DATA seulement). */
  bits?: number;
  value?: number;
  default: number;
  fill: number;
  color?: FieldColor;
  algo?: Crc;
  over: [Pos, Pos];
  /** "if" du fichier : présent si ce champ est présent et non nul / non vide. */
  cond?: string;
  of: string[];
  order?: ByteOrder;
  /** Placement : BIT de départ, 'start' ou 'end'. */
  at?: number | 'start' | 'end';
  /** Placement : juste après ce champ. */
  after?: string;
  /** Rôle copy : champ recopié. */
  sameAs?: string;
  description: string;
  descriptionEn: string;
  /** Sens de chaque valeur ("values" du fichier). */
  values?: Map<number, ValueText>;
  category?: string;
}

/** Texte d'une valeur dans une table {valeur: texte ou {fr, en}} ('' si absente). */
export function valueText(texts: Map<number, ValueText> | undefined, value: number | undefined, language = 'fr'): string {
  if (!texts || value === undefined) return '';
  const text = texts.get(value);
  if (text === undefined || text === null) return '';
  if (typeof text === 'object') return String((language === 'en' ? text.en : text.fr) ?? text.fr ?? text.en ?? '');
  return String(text);
}

/** false pour un champ de taille 0 (gardé dans le fichier pour mémoire, mais absent). */
export const isPresent = (f: FieldSpec) => f.bits !== 0;

/** Taille en octets si elle est entière, sinon undefined. */
export const byteSize = (f: FieldSpec) => (f.bits !== undefined && f.bits % 8 === 0 ? f.bits / 8 : undefined);

/** '2 octet(s)' pour une taille entière en octets, sinon '12 bits'. */
export const bitsText = (bits: number) => (bits % 8 === 0 ? `${bits / 8} octet(s)` : `${bits} bits`);

/** « l'octet 3 » / « le bit 19 ». */
export const positionText = (bit: number) => (bit % 8 === 0 ? `l'octet ${bit / 8}` : `le bit ${bit}`);

/** « à l'octet 3 » / « au bit 19 ». */
export const atText = (bit: number) => (bit % 8 === 0 ? `à l'octet ${bit / 8}` : `au bit ${bit}`);

type Raw = Record<string, unknown>;

// ---------------------------------------------------------------------------
// Lecture d'un champ
// ---------------------------------------------------------------------------

export function parseField(d: unknown, crcs: Record<string, Crc>, kind: string): FieldSpec {
  const input = (d ?? {}) as Raw;
  if (!d || typeof d !== 'object' || !input.name) throw new ProtocolError(`${kind} : chaque champ doit avoir un "name"`);
  // Clé à null = non utilisée : on peut garder toutes les clés dans le fichier
  const o: Raw = Object.fromEntries(Object.entries(input).filter(([, v]) => v !== null && v !== undefined));
  const where = `${kind} : champ '${String(o.name)}'`;
  const f: FieldSpec = {
    name: String(o.name), role: readRole(o, where), default: 0, fill: 0, over: [0, 'end'], of: [],
    description: '', descriptionEn: '',
  };
  readCommon(f, o, where);
  readTexts(f, o, where);
  if (f.role === 'crc') readCrc(f, o, crcs, where);
  readBits(f, o, where);
  switch (f.role) {
    case 'value':
      readValue(f, o, where);
      break;
    case 'field':
      f.default = toInt(o.default ?? 0, `${where} default`);
      break;
    case 'length':
      readLength(f, o, where);
      break;
    case 'na':
      readNa(f, o, where);
      break;
    case 'copy':
      if (!('same_as' in o)) throw new ProtocolError(`${where} : "same_as" manquant (champ recopié)`);
      f.sameAs = String(o.same_as);
      break;
    default:
      break;
  }
  return f;
}

function readTexts(f: FieldSpec, o: Raw, where: string): void {
  f.description = String(o.description ?? '');
  f.descriptionEn = String(o.description_en ?? '');
  if ('category' in o) f.category = String(o.category);
  if (!('values' in o)) return;
  if (typeof o.values !== 'object' || Array.isArray(o.values)) throw new ProtocolError(`${where} : values doit être un objet {valeur: texte}`);
  f.values = new Map(Object.entries(o.values as Record<string, ValueText>).map(([k, v]) => [toInt(k, `${where} values`), v]));
}

function readRole(o: Raw, where: string): FieldRole {
  const role = String(o.role ?? ('value' in o ? 'value' : 'field')).toLowerCase() as FieldRole;
  if (!ROLES.includes(role)) throw new ProtocolError(`${where} : rôle '${role}' inconnu (${ROLES.join(', ')})`);
  return role;
}

function readCommon(f: FieldSpec, o: Raw, where: string): void {
  if (o.color !== undefined && o.color !== null) {
    const color = String(o.color);
    if (!COLORS.includes(color) && !HEX_COLOR.test(color)) {
      throw new ProtocolError(`${where} : couleur '${color}' inconnue (hdr, cmd, crc, na ou #RRGGBB)`);
    }
    f.color = o.color as FieldColor;
  } else if (f.role === 'na') {
    f.color = 'na';
  }
  if (o.order !== undefined && o.order !== null) {
    if (o.order !== 'little' && o.order !== 'big') throw new ProtocolError(`${where} : order doit valoir little ou big`);
    f.order = o.order;
  }
  if (o.if !== undefined && o.if !== null) f.cond = String(o.if);
  readPlace(f, o, where);
}

/** Placement : "at" (octet de départ, "start", "end") ou "after" (nom d'un champ). */
function readPlace(f: FieldSpec, o: Raw, where: string): void {
  const keys = [...BYTE_AT_KEYS, ...BIT_AT_KEYS].filter((k) => k in o);
  if (keys.length && 'after' in o) throw new ProtocolError(`${where} : "at" et "after" ne peuvent pas être utilisés ensemble`);
  if (keys.length > 1) throw new ProtocolError(`${where} : une seule position (${keys.join(', ')})`);
  if (o.after !== undefined && o.after !== null) f.after = String(o.after);
  if (!keys.length || o[keys[0]] === undefined || o[keys[0]] === null) return;
  const key = keys[0];
  const at = o[key];
  if (typeof at === 'string' && PLACES.includes(at.toLowerCase())) {
    f.at = at.toLowerCase() as 'start' | 'end';
    return;
  }
  const unit = BIT_AT_KEYS.includes(key) ? 1 : 8;
  const n = toInt(at, `${where} ${key}`) * unit;
  if (n < 0) {
    const what = unit === 1 ? 'de bit' : "d'octet";
    throw new ProtocolError(`${where} : ${key} doit être un numéro ${what} (0, 1, 2…), "start" ou "end"`);
  }
  f.at = n;
}

function readCrc(f: FieldSpec, o: Raw, crcs: Record<string, Crc>, where: string): void {
  if (o.algo === undefined || o.algo === null) throw new ProtocolError(`${where} : "algo" manquant`);
  const name = String(o.algo);
  const algo = crcs[name] ?? CRC_PRESETS[name];
  if (!algo) throw new ProtocolError(`${where} : CRC '${name}' ni défini dans "crc" ni connu`);
  f.algo = algo;
  const over = o.over ?? [0, 'end'];
  if (!Array.isArray(over) || over.length !== 2) throw new ProtocolError(`${where} : over doit être [début, fin]`);
  f.over = [over[0] as Pos, over[1] as Pos];
}

function readBits(f: FieldSpec, o: Raw, where: string): void {
  const byteKeys = BYTE_SIZE_KEYS.filter((k) => o[k] !== undefined && o[k] !== null);
  const bitKeys = BIT_SIZE_KEYS.filter((k) => o[k] !== undefined && o[k] !== null);
  if (byteKeys.length + bitKeys.length > 1) throw new ProtocolError(`${where} : une seule taille (${[...byteKeys, ...bitKeys].join(', ')})`);
  if (byteKeys.length) f.bits = 8 * toInt(o[byteKeys[0]], `${where} ${byteKeys[0]}`);
  else if (bitKeys.length) f.bits = toInt(o[bitKeys[0]], `${where} ${bitKeys[0]}`);
  else if (f.role === 'crc') f.bits = f.algo!.width;
  else if (f.role !== 'data') throw new ProtocolError(`${where} : "size" manquant (ou LENO / LENb)`);
  if (f.bits !== undefined) checkBits(f, where);
}

function checkBits(f: FieldSpec, where: string): void {
  const maximum = MAX_BYTES[f.role] ?? 4;
  const bits = f.bits!;
  if (!(bits >= 0 && bits <= 8 * maximum)) throw new ProtocolError(`${where} : size doit valoir 0 à ${maximum} octets (${8 * maximum} bits)`);
  if (WHOLE_BYTES.includes(f.role) && bits % 8) throw new ProtocolError(`${where} : un champ ${f.role} doit faire un nombre entier d'octets`);
  if (f.role === 'crc' && bits !== 0 && bits !== f.algo!.width) {
    throw new ProtocolError(`${where} : size ${bits / 8} incompatible avec ${f.algo!.name} (${f.algo!.size} octet(s))`);
  }
}

function readValue(f: FieldSpec, o: Raw, where: string): void {
  if (!('value' in o)) throw new ProtocolError(`${where} : "value" manquant`);
  f.value = toInt(o.value, `${where} value`);
  if (f.value >= 2 ** f.bits!) throw new ProtocolError(`${where} : value ne tient pas sur ${bitsText(f.bits!)}`);
}

function readLength(f: FieldSpec, o: Raw, where: string): void {
  if (o.of === undefined || o.of === null) throw new ProtocolError(`${where} : "of" manquant (champ(s) comptés, ex. "DATA")`);
  f.of = typeof o.of === 'string' ? [o.of] : (o.of as unknown[]).map(String);
}

function readNa(f: FieldSpec, o: Raw, where: string): void {
  f.fill = toInt(o.fill ?? 0, `${where} fill`);
  if (!(f.fill >= 0 && f.fill <= 0xff)) throw new ProtocolError(`${where} : fill doit valoir 0 à 255 (un octet)`);
}

// ---------------------------------------------------------------------------
// Cohérence d'un sens (tx ou rx)
// ---------------------------------------------------------------------------

export function checkLayout(fields: FieldSpec[], kind: string): void {
  checkUniqueNames(fields, kind);
  checkUniqueRoles(fields, kind);
  const index = new Map(fields.map((f, i) => [f.name, i]));
  fields.forEach((f, i) => checkReferences(f, i, index, kind, fields));
  checkVariableData(fields, index, kind);
  checkAlignment(fields, kind);
  checkLengthCounts(fields, kind);
}

export function checkUniqueNames(fields: FieldSpec[], kind: string): void {
  const names = fields.map((f) => f.name);
  const dup = [...new Set(names.filter((n, i) => names.indexOf(n) !== i))].sort();
  if (dup.length) throw new ProtocolError(`${kind} : noms en double : ${dup.join(', ')}`);
}

function checkUniqueRoles(fields: FieldSpec[], kind: string): void {
  for (const role of UNIQUE_ROLES) {
    if (fields.filter((f) => f.role === role && isPresent(f)).length > 1) {
      throw new ProtocolError(`${kind} : un seul champ de rôle '${role}'`);
    }
  }
}

function checkReferences(f: FieldSpec, i: number, index: Map<string, number>, kind: string, all: FieldSpec[]): void {
  if (f.cond && !index.has(f.cond)) throw new ProtocolError(`${kind} : champ '${f.name}' : "if" désigne un champ inconnu '${f.cond}'`);
  if (f.role === 'crc') {
    for (const p of f.over) {
      if (typeof p === 'string' && p !== 'end' && !index.has(p)) {
        throw new ProtocolError(`${kind} : champ '${f.name}' : over désigne un champ inconnu '${p}'`);
      }
    }
  }
  if (f.role === 'copy') {
    const target = index.get(f.sameAs!);
    if (target === undefined) throw new ProtocolError(`${kind} : champ '${f.name}' : same_as désigne un champ inconnu '${f.sameAs}'`);
    if (target > i) throw new ProtocolError(`${kind} : champ '${f.name}' : le champ recopié '${f.sameAs}' doit le précéder`);
    if (!NUMERIC_ROLES.includes(all[target].role)) throw new ProtocolError(`${kind} : champ '${f.name}' : le champ recopié '${f.sameAs}' doit être numérique`);
  }
  if (f.role === 'length') {
    for (const n of f.of) {
      if (!index.has(n)) throw new ProtocolError(`${kind} : champ '${f.name}' : of désigne un champ inconnu '${n}'`);
      if (index.get(n)! < i) throw new ProtocolError(`${kind} : la longueur '${f.name}' doit précéder le champ '${n}'`);
    }
  }
}

function checkVariableData(fields: FieldSpec[], index: Map<string, number>, kind: string): void {
  const data = fields.find((f) => f.role === 'data' && isPresent(f));
  if (!data || data.bits !== undefined || fields.some((f) => f.role === 'length')) return;
  const after = fields.slice(index.get(data.name)! + 1);
  if (after.some((f) => f.bits === undefined)) {
    throw new ProtocolError(`${kind} : après une DATA de taille variable, les champs doivent avoir une taille fixe`);
  }
}

/** DATA et CRC commencent sur un octet, champ conditionnel en octets entiers, trame finie sur un octet. */
function checkAlignment(fields: FieldSpec[], kind: string): void {
  let phase = 0;
  for (const f of fields) {
    if (!isPresent(f)) continue;
    if (f.cond && f.bits && f.bits % 8) {
      throw new ProtocolError(`${kind} : champ '${f.name}' : un champ conditionnel (if) doit faire un nombre entier d'octets`);
    }
    if (WHOLE_BYTES.includes(f.role) && phase) {
      throw new ProtocolError(`${kind} : champ '${f.name}' : doit commencer sur un octet entier (il commence au bit ${phase} d'un octet)`);
    }
    phase = (phase + (f.bits ?? 0)) % 8;
  }
  if (phase) throw new ProtocolError(`${kind} : la trame ne finit pas sur un octet entier (il manque ${8 - phase} bit(s))`);
}

/** Une longueur compte des octets : ensemble, les champs comptés font des octets entiers. */
function checkLengthCounts(fields: FieldSpec[], kind: string): void {
  const byName = new Map(fields.map((f) => [f.name, f]));
  for (const f of fields) {
    if (f.role !== 'length') continue;
    const total = f.of.reduce((s, name) => s + (byName.get(name)!.bits ?? 0), 0);
    if (total % 8) {
      throw new ProtocolError(`${kind} : champ '${f.name}' : les champs comptés par of doivent faire ensemble des octets entiers (${total} bits)`);
    }
  }
}

// ---------------------------------------------------------------------------
// Plage d'octets d'un CRC
// ---------------------------------------------------------------------------

export type Placed = Map<string, [number, number]>;

/** Plage [a, b[ couverte par un CRC (bornes incluses dans le fichier ; "end" = juste avant le CRC). */
export function crcRange(spec: FieldSpec, placed: Placed, crcStart: number): [number, number] {
  const [lo, hi] = spec.over;
  let a: number;
  if (typeof lo === 'string') {
    const p = placed.get(lo);
    if (!p) return [0, 0];
    a = p[0];
  } else {
    a = lo;
  }
  let b: number;
  if (hi === 'end') {
    b = crcStart;
  } else if (typeof hi === 'string') {
    const p = placed.get(hi);
    if (!p) return [0, 0];
    b = p[0] + p[1];
  } else {
    b = hi + 1;
  }
  return [a, Math.max(a, b)];
}
