/**
 * core/protocol/common.ts — Constantes et outils partagés (portage de core/protocol/common.py).
 */
import { parseIntValue } from '../frames';

export const QUERY = 'requête';
export const RESPONSE = 'réponse';
export type FrameKind = typeof QUERY | typeof RESPONSE;
export const KIND_KEYS: Record<FrameKind, 'tx' | 'rx'> = { [QUERY]: 'tx', [RESPONSE]: 'rx' };
export type ByteOrder = 'little' | 'big';

/** Fichier de conf de protocole invalide (message lisible, identique à la version Python). */
export class ProtocolError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ProtocolError';
  }
}

/** Entier lu dans le JSON : nombre, ou texte décimal / "0x..." / "0b...". */
export function toInt(value: unknown, what: string): number {
  if (typeof value === 'number' && Number.isInteger(value)) return value;
  if (typeof value === 'string') {
    try {
      return parseIntValue(value);
    } catch {
      throw new ProtocolError(`${what} : entier attendu, pas '${value}'`);
    }
  }
  throw new ProtocolError(`${what} : entier attendu`);
}

/** Entier -> `size` octets dans l'ordre demandé (jusqu'à 4 octets et au-delà sans perte jusqu'à 2^53). */
export function pack(value: number, size: number, order: ByteOrder): Uint8Array {
  const out = new Uint8Array(size);
  let v = value;
  for (let i = 0; i < size; i++) {
    out[order === 'little' ? i : size - 1 - i] = v % 256;
    v = Math.floor(v / 256);
  }
  return out;
}

export function unpack(raw: Uint8Array, order: ByteOrder): number {
  const bytes = order === 'little' ? Array.from(raw).reverse() : Array.from(raw);
  return bytes.reduce((v, b) => v * 256 + b, 0);
}

export function sameBytes(a: Uint8Array, b: Uint8Array): boolean {
  return a.length === b.length && a.every((x, i) => x === b[i]);
}
