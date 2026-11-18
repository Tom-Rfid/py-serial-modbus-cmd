/**
 * core/protocol/builder.ts — Construction d'une trame (portage de core/protocol/builder.py).
 *
 * 1. chaque champ présent est écrit à la position courante (en bits) ; 2. les CRC en dernier.
 * layout : champs de la variante de trame à construire (Protocol.layout()).
 */
import { coveredBytes, isByteAligned, writeBits } from './bits';
import { pack } from './common';
import { crcRange, isPresent, type FieldSpec, type Placed } from './fields';
import type { Protocol } from './protocol';

export type BuildValues = Record<string, number>;

/** Ce qu'il faut pour écrire une trame (et les valeurs déjà écrites, pour les champs « copy »). */
interface Ctx {
  protocol: Protocol;
  byName: Map<string, FieldSpec>;
  data: Uint8Array;
  values: BuildValues;
  written: Map<string, number>;
}

export function buildFrame(protocol: Protocol, layout: FieldSpec[], data: Uint8Array, values: BuildValues): Uint8Array {
  const ctx: Ctx = { protocol, byName: new Map(layout.map((f) => [f.name, f])), data, values, written: new Map() };
  let out: Uint8Array = new Uint8Array(0);
  let cursor = 0; // en bits
  const placed: Placed = new Map();
  const crcSpecs: FieldSpec[] = [];
  for (const spec of layout) {
    if (!isPresent(spec) || !conditionMet(ctx, spec)) continue;
    const bits = spec.role === 'data' ? 8 * data.length : spec.bits!;
    if (spec.role === 'data' && spec.bits !== undefined && 8 * data.length !== spec.bits) {
      throw new Error(`${spec.name} : ${spec.bits / 8} octet(s) attendus, ${data.length} fournis`);
    }
    out = grow(out, cursor + bits);
    writeField(ctx, spec, out, cursor, bits);
    placed.set(spec.name, coveredBytes(cursor, bits));
    if (spec.role === 'crc') crcSpecs.push(spec);
    cursor += bits;
  }
  writeCrcs(protocol, out, crcSpecs, placed);
  return out;
}

function grow(out: Uint8Array, bits: number): Uint8Array {
  const needed = Math.ceil(bits / 8);
  if (out.length >= needed) return out;
  const bigger = new Uint8Array(needed);
  bigger.set(out);
  return bigger;
}

function writeField(ctx: Ctx, spec: FieldSpec, out: Uint8Array, cursor: number, bits: number): void {
  const protocol = ctx.protocol;
  const start = cursor / 8;
  switch (spec.role) {
    case 'data':
      out.set(ctx.data, start);
      return;
    case 'crc':
      return;
    case 'na':
      if (isByteAligned(cursor, bits)) out.fill(spec.fill, start, start + bits / 8);
      else writeBits(out, cursor, bits, spec.fill ? 2 ** bits - 1 : 0, protocol.bitOrder);
      return;
    default: {
      const value = numericValue(ctx, spec);
      ctx.written.set(spec.name, value);
      const maximum = 2 ** bits - 1;
      if (!(Number.isInteger(value) && value >= 0 && value <= maximum)) {
        throw new Error(`${spec.name} : ${value} hors limites (0 à ${maximum})`);
      }
      if (isByteAligned(cursor, bits)) out.set(protocol.pack(value, bits / 8, spec.order), start);
      else writeBits(out, cursor, bits, value, protocol.bitOrder);
    }
  }
}

function numericValue(ctx: Ctx, spec: FieldSpec): number {
  switch (spec.role) {
    case 'value':
      return spec.value!;
    case 'length':
      return lengthOf(ctx, spec);
    case 'copy':
      return ctx.written.get(spec.sameAs!) ?? 0;
    default: {
      const fallback = spec.role === 'field' ? spec.default : 0;
      return ctx.values[spec.role] ?? ctx.values[spec.name] ?? fallback;
    }
  }
}

function writeCrcs(protocol: Protocol, frame: Uint8Array, specs: FieldSpec[], placed: Placed): void {
  for (const spec of specs) {
    const [start, size] = placed.get(spec.name)!;
    const [a, b] = crcRange(spec, placed, start);
    frame.set(pack(spec.algo!.compute(frame.subarray(a, b)), size, spec.order ?? protocol.byteOrder), start);
  }
}

/** Valeur d'un champ longueur : somme des tailles des champs comptés ("of"), en octets. */
function lengthOf(ctx: Ctx, spec: FieldSpec): number {
  return Math.floor(spec.of.reduce((sum, name) => sum + bitsInFrame(ctx, name), 0) / 8);
}

/** Taille d'un champ dans la trame construite, en bits (0 s'il est absent). */
function bitsInFrame(ctx: Ctx, name: string): number {
  const spec = ctx.byName.get(name)!;
  if (!isPresent(spec) || !conditionMet(ctx, spec)) return 0;
  return spec.role === 'data' ? 8 * ctx.data.length : spec.bits!;
}

/** Condition "if" du champ (vraie s'il n'y en a pas). */
function conditionMet(ctx: Ctx, spec: FieldSpec): boolean {
  if (!spec.cond) return true;
  const target = ctx.byName.get(spec.cond)!;
  if (!isPresent(target)) return false;
  switch (target.role) {
    case 'data':
      return ctx.data.length > 0;
    case 'length':
      return lengthOf(ctx, target) > 0;
    case 'value':
    case 'crc':
    case 'na':
    case 'copy':
      return true;
    default:
      return Boolean(ctx.values[target.role] ?? ctx.values[target.name] ?? target.default);
  }
}
