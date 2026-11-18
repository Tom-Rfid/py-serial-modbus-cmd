/**
 * core/protocol/bits.ts — Champs qui ne tombent pas sur des octets entiers (portage de bits.py).
 *
 * "bit_order" : "msb" (défaut, bit 0 = poids fort de l'octet 0) ou "lsb" (bit 0 = poids faible).
 * En "msb", le premier bit lu est le poids fort de la valeur ; en "lsb", le poids faible.
 */
export type BitOrder = 'msb' | 'lsb';

const shiftOf = (k: number, order: BitOrder) => (order === 'msb' ? 7 - (k % 8) : k % 8);

export function readBits(frame: Uint8Array, start: number, count: number, order: BitOrder): number {
  let value = 0;
  for (let i = 0; i < count; i++) {
    const k = start + i;
    const bit = (frame[Math.floor(k / 8)] >> shiftOf(k, order)) & 1;
    value = order === 'msb' ? value * 2 + bit : value + bit * 2 ** i;
  }
  return value;
}

export function writeBits(buffer: Uint8Array, start: number, count: number, value: number, order: BitOrder): void {
  for (let i = 0; i < count; i++) {
    const weight = order === 'msb' ? count - 1 - i : i;
    const bit = Math.floor(value / 2 ** weight) % 2;
    const k = start + i;
    const index = Math.floor(k / 8);
    const mask = 1 << shiftOf(k, order);
    buffer[index] = bit ? buffer[index] | mask : buffer[index] & ~mask & 0xff;
  }
}

/** [premier octet, nombre d'octets] touchés par les bits start .. start+count-1. */
export function coveredBytes(start: number, count: number): [number, number] {
  const first = Math.floor(start / 8);
  const last = count ? Math.floor((start + count - 1) / 8) : first - 1;
  return [first, last - first + 1];
}

export const isByteAligned = (start: number, count: number) => start % 8 === 0 && count % 8 === 0;
