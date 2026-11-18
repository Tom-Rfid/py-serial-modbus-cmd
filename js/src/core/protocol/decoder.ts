/**
 * core/protocol/decoder.ts — Décodage d'une trame (portage de core/protocol/decoder.py).
 *
 * Position courante en bits. Ne lève jamais d'erreur : les problèmes sont dans Decoded.errors.
 */
import { toHex } from '../frames';
import { coveredBytes, isByteAligned, readBits } from './bits';
import { pack, sameBytes, type FrameKind } from './common';
import { Decoded, type DecodedField } from './decoded';
import { crcRange, isPresent, valueText, type FieldSpec, type Placed } from './fields';
import type { Protocol } from './protocol';

export function decodeFrame(protocol: Protocol, layout: FieldSpec[], kind: FrameKind, frame: Uint8Array): Decoded {
  const d = new Decoded(kind);
  let cursor = 0; // en bits
  const placed: Placed = new Map();
  const crcs: [FieldSpec, DecodedField][] = [];
  for (let i = 0; i < layout.length; i++) {
    const spec = layout[i];
    if (!isPresent(spec) || (spec.cond && !present(spec.cond, d))) continue;
    const bits = spec.role === 'data' ? 8 * dataSize(spec, i, layout, d, frame, Math.floor(cursor / 8)) : spec.bits!;
    if (spec.role === 'data' && bits === 0) continue; // pas de données : DATA absente
    const [start, size] = coveredBytes(cursor, bits);
    if (start + size > frame.length) {
      truncated(d, spec, start, frame.slice(start, start + size), size);
      return d;
    }
    const field = decodeField(protocol, spec, frame, cursor, bits, d);
    if (spec.role === 'crc') crcs.push([spec, field]);
    d.fields.push(field);
    placed.set(spec.name, [start, size]);
    cursor += bits;
  }
  checkCrcs(protocol, frame, crcs, placed, d);
  d.complete = true;
  d.extra = frame.slice(Math.ceil(cursor / 8));
  return d;
}

function decodeField(protocol: Protocol, spec: FieldSpec, frame: Uint8Array, cursor: number, bits: number, d: Decoded): DecodedField {
  const [start, size] = coveredBytes(cursor, bits);
  const field: DecodedField = {
    name: spec.name, start, raw: frame.slice(start, start + size), note: '', role: spec.role, color: spec.color,
    bitStart: cursor, bits, meaning: '',
  };
  switch (spec.role) {
    case 'data':
      field.note = `${size} octets`;
      break;
    case 'na':
      field.note = 'non lu';
      break;
    case 'crc':
      break;
    default:
      field.value = isByteAligned(cursor, bits)
        ? protocol.unpack(frame.subarray(start, start + bits / 8), spec.order)
        : readBits(frame, cursor, bits, protocol.bitOrder);
      if (spec.role === 'value') checkFixed(protocol, spec, field, d);
      else if (spec.role === 'copy') checkCopy(spec, field, d);
      field.meaning = valueText(spec.values, field.value, protocol.language);
  }
  field.description = protocol.language === 'en' && spec.descriptionEn ? spec.descriptionEn : spec.description;
  return field;
}

/** Un champ recopié doit valoir le champ d'origine (ex. longueur répétée). */
function checkCopy(spec: FieldSpec, field: DecodedField, d: Decoded): void {
  const expected = d.get(spec.sameAs!);
  field.ok = field.value === expected;
  if (!field.ok) {
    field.note = `attendu ${expected} (comme ${spec.sameAs})`;
    d.errors.push(`${spec.name} différent de ${spec.sameAs}`);
  }
}

function checkFixed(protocol: Protocol, spec: FieldSpec, field: DecodedField, d: Decoded): void {
  field.ok = field.value === spec.value;
  if (field.ok) return;
  const bits = spec.bits!;
  field.note = bits % 8 === 0
    ? `attendu ${toHex(protocol.pack(spec.value!, bits / 8, spec.order))}`
    : `attendu 0b${spec.value!.toString(2).padStart(bits, '0')}`;
  d.errors.push(`${spec.name} différent de 0x${spec.value!.toString(16).toUpperCase().padStart(Math.ceil(bits / 4), '0')}`);
}

function truncated(d: Decoded, spec: FieldSpec, start: number, raw: Uint8Array, size: number): void {
  if (spec.role === 'data') {
    d.fields.push({ name: spec.name, start, raw, role: 'data', color: spec.color, note: `${raw.length}/${size} octets` });
    d.errors.push(`données tronquées : ${raw.length} octets sur ${size}`);
  } else {
    d.errors.push(`trame tronquée : ${spec.name} incomplet`);
  }
}

function checkCrcs(protocol: Protocol, frame: Uint8Array, crcs: [FieldSpec, DecodedField][], placed: Placed, d: Decoded): void {
  for (const [spec, field] of crcs) {
    const [a, b] = crcRange(spec, placed, field.start);
    const expected = pack(spec.algo!.compute(frame.subarray(a, b)), spec.bits! / 8, spec.order ?? protocol.byteOrder);
    field.ok = sameBytes(field.raw, expected);
    if (!field.ok) {
      field.note = `attendu ${toHex(expected)}`;
      d.errors.push(`${spec.name} incorrect`);
    }
  }
}

/** Condition "if" au décodage : le champ nommé a été lu et n'est pas vide / nul. */
function present(name: string, d: Decoded): boolean {
  const f = d.fields.find((x) => x.name === name);
  if (!f) return false;
  if (f.role === 'data') return f.raw.length > 0;
  if (f.value !== undefined && f.role !== 'value') return f.value !== 0;
  return true;
}

/** Taille de DATA en octets : d'après le champ longueur, fixe, ou le reste de la trame. */
function dataSize(spec: FieldSpec, i: number, layout: FieldSpec[], d: Decoded, frame: Uint8Array, pos: number): number {
  const length = layout.find((x) => x.role === 'length' && isPresent(x) && x.of.includes(spec.name));
  if (length) return sizeFromLength(spec, length, layout, d);
  if (spec.bits !== undefined) return spec.bits / 8;
  return remainingSize(spec, i, layout, frame, pos);
}

function sizeFromLength(spec: FieldSpec, length: FieldSpec, layout: FieldSpec[], d: Decoded): number {
  const value = d.get(length.name);
  if (value === undefined) return 0;
  const others = Math.floor(
    layout.filter((x) => length.of.includes(x.name) && x.name !== spec.name).reduce((s, x) => s + (x.bits ?? 0), 0) / 8,
  );
  return Math.max(0, value - others);
}

function remainingSize(spec: FieldSpec, i: number, layout: FieldSpec[], frame: Uint8Array, pos: number): number {
  const after = layout.slice(i + 1).filter((x) => x.bits);
  const fixed = Math.floor(after.filter((x) => x.cond !== spec.name).reduce((s, x) => s + x.bits!, 0) / 8);
  const conditional = Math.floor(after.filter((x) => x.cond === spec.name).reduce((s, x) => s + x.bits!, 0) / 8);
  const rest = frame.length - pos - fixed;
  return rest > conditional ? rest - conditional : 0;
}
