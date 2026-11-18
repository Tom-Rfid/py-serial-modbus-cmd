/**
 * core/protocol/protocol.ts — Un protocole décrit par un fichier de conf (portage de core/protocol/protocol.py).
 *
 *   const p = new Protocol(conf);
 *   const frame = p.buildQuery(5, 0x00000004, Uint8Array.of(1));
 *   const d = p.decode(frame, QUERY);     // d.requestId, d.commandId, d.data?.raw, d.ok, d.variant
 *
 * Variantes de trame : "tx" / "rx" peuvent décrire plusieurs formats, reconnus à leurs
 * octets fixes (M-Bus : E5 / 10… / 68…, Profibus : SD1 à SD4) :
 *   "rx": {"variants": [ {"name": "Accusé", "fields": [...]}, {"name": "Long", "fields": [...]} ]}
 */
import { isByteAligned, readBits, type BitOrder } from './bits';
import { buildFrame, type BuildValues } from './builder';
import { KIND_KEYS, ProtocolError, QUERY, RESPONSE, pack, toInt, unpack, type ByteOrder, type FrameKind } from './common';
import { parseCrc, type Crc } from './crc';
import type { Decoded } from './decoded';
import { decodeFrame } from './decoder';
import { parseEncoding, type AsciiHex } from './encoding';
import { checkLayout, checkUniqueNames, isPresent, parseField, valueText, type FieldRole, type FieldSpec, type ValueText } from './fields';
import { orderFields } from './placement';

/** Un format de trame : son nom (vide s'il n'y en a qu'un) et ses champs. */
export interface Variant {
  name: string;
  fields: FieldSpec[];
  description: string;
  descriptionEn: string;
}

export type Segment = [number, number, string];

export class Protocol {
  readonly name: string;
  readonly description: string;
  readonly descriptionEn: string;
  /** Langue des textes ("values", descriptions, erreurs) : 'fr' ou 'en'. */
  language = 'fr';
  readonly byteOrder: ByteOrder;
  /** Sens de lecture des bits d'un octet pour les champs en bits (voir bits.ts). */
  readonly bitOrder: BitOrder;
  /** Codage sur la ligne (Modbus ASCII), ou undefined (binaire). */
  readonly encoding?: AsciiHex;
  readonly crcs: Record<string, Crc>;
  /** Formats de trame de chaque sens ; layouts = le premier de chaque sens. */
  readonly variants = {} as Record<FrameKind, Variant[]>;
  readonly layouts = {} as Record<FrameKind, FieldSpec[]>;
  /** Dossier des commandes Msg_*.json, tel qu'écrit dans le fichier (relatif au fichier). */
  readonly commands?: string;
  /** Codes d'erreur du fichier : {code: texte, ou {fr, en}}. */
  readonly errors: Record<number, ValueText> = {};
  /** Catégories ("categories" du fichier) : {code: texte, ou {fr, en}}. */
  readonly categories: Record<string, ValueText> = {};

  constructor(readonly conf: Record<string, unknown>, fileName?: string) {
    if (!conf || typeof conf !== 'object' || Array.isArray(conf)) throw new ProtocolError('le fichier doit contenir un objet JSON');
    this.name = String(conf.name || stemOf(fileName));
    this.description = String(conf.description || '');
    this.descriptionEn = String(conf.description_en || '');
    this.byteOrder = readByteOrder(conf);
    this.bitOrder = readBitOrder(conf);
    this.encoding = parseEncoding(conf);
    this.crcs = readCrcs(conf);
    for (const kind of [QUERY, RESPONSE] as FrameKind[]) {
      this.variants[kind] = this.readVariants(conf, kind);
      this.layouts[kind] = this.variants[kind][0].fields;
    }
    if (conf.commands) this.commands = String(conf.commands);
    for (const [k, v] of Object.entries((conf.errors ?? {}) as Record<string, ValueText>)) this.errors[toInt(k, 'errors')] = v;
    Object.assign(this.categories, (conf.categories ?? {}) as Record<string, ValueText>);
  }

  // --- lecture du fichier
  /** "tx" / "rx" : une liste de champs, ou {"variants": [{"name", "fields"}, ...]}. */
  private readVariants(conf: Record<string, unknown>, kind: FrameKind): Variant[] {
    const key = KIND_KEYS[kind];
    const items = conf[key];
    if (items && typeof items === 'object' && !Array.isArray(items) && 'variants' in items) {
      return this.readVariantList((items as Record<string, unknown>).variants, key);
    }
    return [{ name: '', fields: this.readFields(items, key), description: '', descriptionEn: '' }];
  }

  private readVariantList(variants: unknown, key: string): Variant[] {
    if (!Array.isArray(variants) || !variants.length) throw new ProtocolError(`"${key}" : variants doit être une liste de formats de trame`);
    const out: Variant[] = [];
    for (const v of variants as Record<string, unknown>[]) {
      if (!v || typeof v !== 'object' || !v.name) throw new ProtocolError(`"${key}" : chaque variante doit avoir un "name"`);
      const name = String(v.name);
      out.push({
        name,
        fields: this.readFields(v.fields, `${key} [${name}]`),
        description: String(v.description ?? ''),
        descriptionEn: String(v.description_en ?? ''),
      });
    }
    const names = out.map((v) => v.name);
    const duplicates = [...new Set(names.filter((n, i) => names.indexOf(n) !== i))].sort();
    if (duplicates.length) throw new ProtocolError(`"${key}" : variantes en double : ${duplicates.join(', ')}`);
    return out;
  }

  private readFields(items: unknown, where: string): FieldSpec[] {
    if (!Array.isArray(items) || !items.length) throw new ProtocolError(`"${where}" : liste de champs attendue`);
    const parsed = items.map((d) => parseField(d, this.crcs, where));
    checkUniqueNames(parsed, where); // avant le placement, qui s'appuie sur les noms
    const fields = orderFields(parsed, where); // "at" / "after" : ordre final des octets
    checkLayout(fields, where);
    return fields;
  }

  // --- ordre des octets
  pack(value: number, size: number, order?: ByteOrder): Uint8Array {
    return pack(value, size, order ?? this.byteOrder);
  }

  unpack(raw: Uint8Array, order?: ByteOrder): number {
    return unpack(raw, order ?? this.byteOrder);
  }

  // --- informations sur les champs
  /** Noms des variantes de trame (liste vide s'il n'y a qu'un format). */
  variantNames(kind: FrameKind): string[] {
    const names = this.variants[kind].map((v) => v.name);
    return names.length > 1 || names[0] ? names : [];
  }

  /** Champs d'une variante (par son nom) ; la première si variant est vide. */
  layout(kind: FrameKind, variant?: string): FieldSpec[] {
    if (!variant) return this.layouts[kind];
    const found = this.variants[kind].find((v) => v.name === variant);
    if (!found) throw new Error(`variante de trame inconnue : ${variant}`);
    return found.fields;
  }

  /** Champ par son nom, cherché dans toutes les variantes. */
  field(kind: FrameKind, name: string): FieldSpec {
    for (const v of this.variants[kind]) {
      const f = v.fields.find((x) => x.name === name);
      if (f) return f;
    }
    throw new Error(name);
  }

  /** Champ d'un rôle dans la première variante qui en a un, ou undefined. */
  spec(kind: FrameKind, role: FieldRole): FieldSpec | undefined {
    for (const v of this.variants[kind]) {
      const f = v.fields.find((x) => x.role === role && isPresent(x));
      if (f) return f;
    }
    return undefined;
  }

  has(kind: FrameKind, role: FieldRole): boolean {
    return this.spec(kind, role) !== undefined;
  }

  /** Valeur maximale d'un champ (255 pour un REQUEST ID sur 1 octet), ou undefined. */
  maxValue(kind: FrameKind, role: FieldRole): number | undefined {
    const f = this.spec(kind, role);
    return f ? 2 ** f.bits! - 1 : undefined;
  }

  /** CRC principal (premier CRC des requêtes) et son ordre d'octets. */
  get mainCrc(): { algo?: Crc; order: ByteOrder } {
    const f = this.spec(QUERY, 'crc');
    return f ? { algo: f.algo, order: f.order ?? this.byteOrder } : { order: this.byteOrder };
  }

  /** CRC principal de `data`, en octets (vide si le protocole n'a pas de CRC). */
  crcBytes(data: Uint8Array): Uint8Array {
    const { algo, order } = this.mainCrc;
    return algo ? pack(algo.compute(data), algo.size, order) : new Uint8Array();
  }

  /** Délimiteur de fin de trame sur la ligne (Modbus ASCII : CR LF), ou undefined. */
  get frameEnd(): Uint8Array | undefined {
    return this.encoding && this.encoding.end.length ? this.encoding.end : undefined;
  }

  /** Texte d'une valeur dans une table {valeur: texte ou {fr, en}}, dans la langue choisie. */
  text(texts: Record<number, ValueText> | Map<number, ValueText>, value: number): string {
    const map = texts instanceof Map ? texts : new Map(Object.entries(texts).map(([k, v]) => [Number(k), v]));
    return valueText(map, value, this.language);
  }

  /** Codes d'erreur du fichier : {code: texte} dans la langue choisie. */
  errorTexts(): Record<number, string> {
    const out: Record<number, string> = {};
    for (const code of Object.keys(this.errors)) out[Number(code)] = this.text(this.errors, Number(code));
    return out;
  }

  /** Texte d'une catégorie ("categories" du fichier), ou le code lui-même. */
  categoryText(code: string): string {
    if (!(code in this.categories)) return code;
    return valueText(new Map([[0, this.categories[code]]]), 0, this.language) || code;
  }

  // --- trames
  /** La trame commence-t-elle comme ce protocole (octets fixes du début d'une variante) ? */
  matches(frame: Uint8Array, kind: FrameKind): boolean {
    if (!frame.length) return false;
    if (this.encoding) {
      const [ok, binary] = this.encoding.prefix(frame);
      if (!ok) return false;
      if (!binary.length) return true;
      frame = binary;
    }
    return this.variants[kind].some((v) => this.layoutMatches(frame, v.fields));
  }

  private layoutMatches(frame: Uint8Array, layout: FieldSpec[]): boolean {
    let cursor = 0; // en bits
    for (const f of layout) {
      if (!isPresent(f)) continue;
      if (f.bits === undefined || f.cond) break; // position des champs suivants inconnue
      if (f.role === 'value' && !this.fixedMatches(frame, f, cursor)) return false;
      cursor += f.bits;
    }
    return true;
  }

  /** Octet(s) fixe(s) à la bonne valeur ; une trame trop courte est comparée sur ce qu'elle a. */
  private fixedMatches(frame: Uint8Array, f: FieldSpec, cursor: number): boolean {
    const bits = f.bits!;
    if (isByteAligned(cursor, bits)) {
      const raw = frame.subarray(cursor / 8, cursor / 8 + bits / 8);
      const expected = this.pack(f.value!, bits / 8, f.order).subarray(0, raw.length);
      return !raw.length || raw.every((b, i) => b === expected[i]);
    }
    if (Math.ceil((cursor + bits) / 8) > frame.length) return true;
    return readBits(frame, cursor, bits, this.bitOrder) === f.value;
  }

  /**
   * Trame complète. values : {rôle ou nom de champ: valeur}, ex. { request_id: 5, command_id: 4 }.
   * variant : nom de la variante de trame (la première par défaut).
   */
  build(kind: FrameKind, data: Uint8Array = new Uint8Array(), values: BuildValues = {}, variant?: string): Uint8Array {
    const binary = buildFrame(this, this.layout(kind, variant), data, values);
    return this.encoding ? this.encoding.wrap(binary) : binary;
  }

  buildQuery(requestId = 0, commandId = 0, data: Uint8Array = new Uint8Array()): Uint8Array {
    return this.build(QUERY, data, { request_id: requestId, command_id: commandId });
  }

  buildResponse(requestId = 0, error = 0, data: Uint8Array = new Uint8Array()): Uint8Array {
    return this.build(RESPONSE, data, { request_id: requestId, error });
  }

  /** Décode une trame (variante reconnue à ses octets fixes). Ne lève jamais d'erreur. */
  decode(frame: Uint8Array, kind: FrameKind): Decoded {
    if (!this.encoding) return this.decodeBinary(frame, kind);
    const [binary, problems, complete, extra] = this.encoding.unwrap(frame);
    const d = this.decodeBinary(binary, kind);
    d.errors = [...problems, ...d.errors];
    d.complete = d.complete && complete;
    const all = new Uint8Array(d.extra.length + extra.length);
    all.set(d.extra, 0);
    all.set(extra, d.extra.length);
    d.extra = all;
    d.encoded = frame.slice();
    d.binary = binary;
    return d;
  }

  private decodeBinary(frame: Uint8Array, kind: FrameKind): Decoded {
    let candidates = this.variants[kind].filter((v) => this.layoutMatches(frame, v.fields));
    if (!candidates.length) candidates = this.variants[kind].slice(0, 1);
    let first: Decoded | undefined;
    for (const v of candidates) {
      const d = decodeFrame(this, v.fields, kind, frame);
      d.variant = v.name;
      if (d.ok) return d;
      first = first ?? d;
    }
    return first!;
  }

  /** Couleurs à appliquer à la trame telle qu'elle passe sur la ligne (codage ASCII compris). */
  displaySegments(decoded: Decoded, segments: Segment[]): Segment[] {
    if (!this.encoding || !decoded.encoded.length) return segments;
    return this.encoding.rawSegments(segments, decoded.binary.length);
  }
}

function stemOf(fileName?: string): string {
  if (!fileName) return 'protocole';
  return (fileName.split(/[\\/]/).pop() ?? fileName).replace(/\.[^.]*$/, '');
}

function readByteOrder(conf: Record<string, unknown>): ByteOrder {
  const order = conf.byte_order ?? 'little';
  if (order !== 'little' && order !== 'big') throw new ProtocolError('byte_order doit valoir little ou big');
  return order;
}

function readBitOrder(conf: Record<string, unknown>): BitOrder {
  const order = conf.bit_order ?? 'msb';
  if (order !== 'msb' && order !== 'lsb') throw new ProtocolError('bit_order doit valoir msb ou lsb');
  return order;
}

function readCrcs(conf: Record<string, unknown>): Record<string, Crc> {
  const section = conf.crc ?? {};
  if (typeof section !== 'object' || Array.isArray(section)) throw new ProtocolError('"crc" doit être un objet {nom: définition}');
  const out: Record<string, Crc> = {};
  for (const [name, spec] of Object.entries(section as Record<string, unknown>)) out[name] = parseCrc(name, spec);
  return out;
}
