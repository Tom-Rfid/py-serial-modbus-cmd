/**
 * core/protocol/crc.ts — CRC 8 / 16 / 32 bits et sommes simples (portage de core/protocol/crc.py).
 *
 * Modèle standard des catalogues (reveng) : width, poly (forme normale), init,
 * refin (octets lus bit de poids faible en premier), refout (résultat réfléchi), xorout.
 */
import { ProtocolError, toInt } from './common';

function reflect(value: number, width: number): number {
  let out = 0;
  for (let i = 0; i < width; i++) {
    out = ((out << 1) | (value & 1)) >>> 0;
    value >>>= 1;
  }
  return out >>> 0;
}

export type CrcKind = 'crc' | 'sum8' | 'sum8_2c' | 'xor8' | 'sum16';

export class Crc {
  constructor(
    readonly name: string,
    readonly width = 16,
    readonly poly = 0,
    readonly init = 0,
    readonly refin = false,
    readonly refout = false,
    readonly xorout = 0,
    readonly kind: CrcKind = 'crc',
  ) {}

  /** Taille du résultat en octets. */
  get size(): number {
    return this.width / 8;
  }

  compute(data: Uint8Array): number {
    return this.kind === 'crc' ? this.crc(data) : this.sum(data);
  }

  private sum(data: Uint8Array): number {
    let total = 0;
    switch (this.kind) {
      case 'sum8':
        for (const b of data) total += b;
        return total & 0xff;
      case 'sum8_2c': // complément à 2 : la somme trame + checksum vaut 0
        for (const b of data) total += b;
        return -total & 0xff;
      case 'xor8':
        for (const b of data) total ^= b;
        return total;
      case 'sum16':
        for (const b of data) total += b;
        return total & 0xffff;
      default:
        throw new Error(`somme inconnue : ${this.kind}`);
    }
  }

  private crc(data: Uint8Array): number {
    const w = this.width;
    const mask = w === 32 ? 0xffffffff : (1 << w) - 1;
    const topBit = w === 32 ? 0x80000000 : 1 << (w - 1);
    let register = (this.init & mask) >>> 0;
    for (let byte of data) {
      if (this.refin) byte = reflect(byte, 8);
      register = (register ^ (byte << (w - 8))) >>> 0; // l'octet entre par le haut du registre
      for (let i = 0; i < 8; i++) {
        const high = (register & topBit) !== 0;
        register = ((register << 1) & mask) >>> 0;
        if (high) register = ((register ^ this.poly) & mask) >>> 0;
      }
    }
    if (this.refout) register = reflect(register, w);
    return ((register ^ this.xorout) & mask) >>> 0;
  }
}

/** Noms prêts à l'emploi (valeur de contrôle compute("123456789") vérifiée par les tests). */
export const CRC_PRESETS: Record<string, Crc> = {
  crc16_modbus: new Crc('crc16_modbus', 16, 0x8005, 0xffff, true, true, 0),
  crc16_ccitt_false: new Crc('crc16_ccitt_false', 16, 0x1021, 0xffff, false, false, 0),
  crc16_xmodem: new Crc('crc16_xmodem', 16, 0x1021, 0, false, false, 0),
  crc16_kermit: new Crc('crc16_kermit', 16, 0x1021, 0, true, true, 0),
  crc8: new Crc('crc8', 8, 0x07, 0, false, false, 0),
  crc8_maxim: new Crc('crc8_maxim', 8, 0x31, 0, true, true, 0),
  crc32: new Crc('crc32', 32, 0x04c11db7, 0xffffffff, true, true, 0xffffffff),
  crc32_mpeg2: new Crc('crc32_mpeg2', 32, 0x04c11db7, 0xffffffff, false, false, 0),
  sum8: new Crc('sum8', 8, 0, 0, false, false, 0, 'sum8'),
  sum8_2c: new Crc('sum8_2c', 8, 0, 0, false, false, 0, 'sum8_2c'),
  xor8: new Crc('xor8', 8, 0, 0, false, false, 0, 'xor8'),
  sum16: new Crc('sum16', 16, 0, 0, false, false, 0, 'sum16'),
};

/** Une entrée de la section "crc" : nom prêt à l'emploi, { preset }, ou les paramètres. */
export function parseCrc(name: string, spec: unknown): Crc {
  if (typeof spec === 'string') return preset(name, spec);
  if (!spec || typeof spec !== 'object' || Array.isArray(spec)) {
    throw new ProtocolError(`crc '${name}' : nom de CRC ou objet attendu`);
  }
  const s = spec as Record<string, unknown>;
  if ('preset' in s) return parseCrc(name, s.preset);
  return custom(name, s);
}

function preset(name: string, value: string): Crc {
  const p = CRC_PRESETS[value];
  if (!p) throw new ProtocolError(`crc '${name}' : '${value}' inconnu (connus : ${Object.keys(CRC_PRESETS).join(', ')})`);
  return p;
}

function custom(name: string, s: Record<string, unknown>): Crc {
  const width = toInt(s.width ?? 16, `crc '${name}' width`);
  if (![8, 16, 32].includes(width)) throw new ProtocolError(`crc '${name}' : width doit valoir 8, 16 ou 32`);
  return new Crc(
    name,
    width,
    toInt(s.poly ?? 0, `crc '${name}' poly`) >>> 0,
    toInt(s.init ?? 0, `crc '${name}' init`) >>> 0,
    Boolean(s.refin),
    Boolean(s.refout),
    toInt(s.xorout ?? 0, `crc '${name}' xorout`) >>> 0,
  );
}
