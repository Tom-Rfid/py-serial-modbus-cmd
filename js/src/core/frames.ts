/**
 * core/frames.ts — Construction des trames.
 *
 * Portage fidèle de core/frames.py : transforme la définition d'un message
 * (Msg_*.json) et les valeurs saisies en octets à envoyer.
 *
 *   encodeParam()  une valeur -> octets selon son type (u8, u16be, enum...)
 *   checksum()     calcul d'un checksum (xor8, sum8, crc16_modbus...)
 *   buildFrame()   trame complète d'un message
 *   defaultsFor()  valeurs par défaut des paramètres
 *
 * Les deux implémentations (Python et TypeScript) sont vérifiées contre
 * tests/vectors.json : elles doivent produire exactement les mêmes octets.
 * Toute modification ici doit être reportée dans core/frames.py.
 */
import type { ChecksumAlgo, IntType, MessageDef, ParamDef, ParamValue, ParamValues, ParamType } from './types';

export const CHECKSUMS: ChecksumAlgo[] = ['xor8', 'sum8', 'sum8_2c', 'crc8', 'crc16_modbus'];
export const TRUTHY = ['1', 'true', 'on', 'oui', 'yes'];

// Taille (octets), signe et ordre des octets de chaque type entier.
// le = little endian (poids faible en premier), sinon big endian.
const INT_SPECS: Record<IntType, { size: 1 | 2 | 4; signed: boolean; le: boolean }> = {
  u8: { size: 1, signed: false, le: false },
  i8: { size: 1, signed: true, le: false },
  u16be: { size: 2, signed: false, le: false },
  u16le: { size: 2, signed: false, le: true },
  i16be: { size: 2, signed: true, le: false },
  i16le: { size: 2, signed: true, le: true },
  u32be: { size: 4, signed: false, le: false },
  u32le: { size: 4, signed: false, le: true },
  i32be: { size: 4, signed: true, le: false },
  i32le: { size: 4, signed: true, le: true },
};

/** Vrai si `t` est un type entier (u8, i16le...). */
export function isIntType(t: string): t is IntType {
  return t in INT_SPECS;
}

/** Comme int(s, 0) en Python : 12, 0x0C, 0b1100, 0o14, 1_000, et 010 (décimal). */
export function parseIntValue(value: ParamValue): number {
  // Les « _ » sont des séparateurs visuels (1_000), comme en Python
  const s = String(value).trim().replace(/_/g, '');
  // signe facultatif, puis : 0x… (hexa) | 0b… (binaire) | 0o… (octal) | chiffres (décimal)
  const m = /^([+-]?)(?:0x([0-9a-f]+)|0b([01]+)|0o([0-7]+)|(\d+))$/i.exec(s);
  if (!m) throw new Error(`'${value}' n'est pas un nombre`);
  const [, sign, hex, bin, oct, dec] = m;
  const n = hex !== undefined ? parseInt(hex, 16)
    : bin !== undefined ? parseInt(bin, 2)
    : oct !== undefined ? parseInt(oct, 8)
    : parseInt(dec, 10);
  return sign === '-' ? -n : n;
}

/** 'AA 55', 'AA55', '0xAA,0x55' -> Uint8Array */
export function parseHex(text: string): Uint8Array {
  const cleaned = String(text).replace(/0x/gi, '').replace(/,/g, ' ');
  const out: number[] = [];
  for (const tok of cleaned.split(/\s+/).filter(Boolean)) {
    if (tok.length % 2 !== 0 || !/^[0-9a-f]+$/i.test(tok)) throw new Error(`hexa invalide : '${text}'`);
    for (let i = 0; i < tok.length; i += 2) out.push(parseInt(tok.slice(i, i + 2), 16));
  }
  return Uint8Array.from(out);
}

/**
 * Encode un entier sur 1, 2 ou 4 octets selon `type`.
 * Lève une erreur si la valeur ne tient pas dans le type (ex. 300 en u8).
 */
export function packInt(type: IntType, v: number): Uint8Array {
  const { size, signed, le } = INT_SPECS[type];
  const bits = size * 8;
  const min = signed ? -(2 ** (bits - 1)) : 0;
  const max = signed ? 2 ** (bits - 1) - 1 : 2 ** bits - 1;
  if (!Number.isInteger(v) || v < min || v > max) throw new Error(`${v} hors limites pour ${type}`);
  // DataView écrit l'entier avec le bon signe et le bon ordre d'octets
  const buf = new DataView(new ArrayBuffer(size));
  if (size === 1) signed ? buf.setInt8(0, v) : buf.setUint8(0, v);
  else if (size === 2) signed ? buf.setInt16(0, v, le) : buf.setUint16(0, v, le);
  else signed ? buf.setInt32(0, v, le) : buf.setUint32(0, v, le);
  return new Uint8Array(buf.buffer);
}

/**
 * Encode la valeur d'UN paramètre.
 *   name  : nom du paramètre (pour les messages d'erreur)
 *   pdef  : sa définition dans le JSON, ex. { type: 'u16be', max: 1023 }
 *   value : valeur saisie
 * Lève une erreur lisible (« led : 9 > max (8) ») si la valeur est invalide.
 */
export function encodeParam(name: string, pdef: ParamDef, value: ParamValue): Uint8Array {
  // Type par défaut : un octet non signé. Les majuscules sont acceptées (U8, RAW).
  const t = String(pdef.type ?? 'u8').toLowerCase() as ParamType;
  // bool : 1 octet, 1 si la valeur est « vraie » (true, 1, oui, on...), sinon 0
  if (t === 'bool') {
    return Uint8Array.of(TRUTHY.includes(String(value).toLowerCase()) ? 1 : 0);
  }
  // enum : libellé de "choices" (ex. 'on' -> 1) ou directement un nombre
  if (t === 'enum') {
    const choices = pdef.choices ?? {};
    const key = String(value);
    const v = key in choices ? choices[key] : parseIntValue(value);
    return wrap(name, () => packInt(pdef.size ?? 'u8', v));
  }
  // entiers : conversion, contrôle des bornes min / max, puis encodage
  if (isIntType(t)) {
    const v = wrap(name, () => parseIntValue(value));
    if (pdef.min !== undefined && v < parseIntValue(pdef.min)) throw new Error(`${name} : ${v} < min (${pdef.min})`);
    if (pdef.max !== undefined && v > parseIntValue(pdef.max)) throw new Error(`${name} : ${v} > max (${pdef.max})`);
    return wrap(name, () => packInt(t, v));
  }
  // hex / raw : octets bruts saisis en hexa, sans conversion, longueur libre
  if (t === 'hex' || t === 'raw') {
    return wrap(name, () => parseHex(String(value)));
  }
  // ascii : 1 caractère = 1 octet (latin-1). Avec "length" : longueur fixe,
  // texte tronqué ou complété par des 0x00.
  if (t === 'ascii') {
    const s = String(value);
    let bytes = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) {
      const c = s.charCodeAt(i);
      if (c > 0xff) throw new Error(`${name} : caractère '${s[i]}' non encodable (latin-1)`);
      bytes[i] = c;
    }
    if (pdef.length) {
      const fixed = new Uint8Array(pdef.length);
      fixed.set(bytes.subarray(0, pdef.length));
      bytes = fixed;
    }
    return bytes;
  }
  throw new Error(`${name} : type inconnu '${t}'`);
}

/** Exécute `fn` et préfixe une éventuelle erreur par le nom du paramètre. */
function wrap<T>(name: string, fn: () => T): T {
  try {
    return fn();
  } catch (e) {
    throw new Error(`${name} : ${(e as Error).message}`);
  }
}

/** Calcule le checksum `algo` sur `data`. */
export function checksum(algo: ChecksumAlgo, data: Uint8Array): Uint8Array {
  switch (algo) {
    // somme des octets, on garde l'octet de poids faible
    case 'sum8':
      return Uint8Array.of(data.reduce((a, b) => a + b, 0) & 0xff);
    // complément à 2 : somme(data) + checksum = 0 (modulo 256)
    case 'sum8_2c':
      return Uint8Array.of(-data.reduce((a, b) => a + b, 0) & 0xff);
    // OU exclusif de tous les octets
    case 'xor8':
      return Uint8Array.of(data.reduce((a, b) => a ^ b, 0));
    // CRC-8 : polynôme 0x07, valeur initiale 0x00
    case 'crc8': {
      let crc = 0;
      for (const b of data) {
        crc ^= b;
        for (let i = 0; i < 8; i++) crc = crc & 0x80 ? ((crc << 1) ^ 0x07) & 0xff : (crc << 1) & 0xff;
      }
      return Uint8Array.of(crc);
    }
    // CRC-16 Modbus : polynôme 0xA001, initial 0xFFFF, envoyé poids faible en premier
    case 'crc16_modbus': {
      let crc = 0xffff;
      for (const b of data) {
        crc ^= b;
        for (let i = 0; i < 8; i++) crc = crc & 1 ? (crc >>> 1) ^ 0xa001 : crc >>> 1;
      }
      return Uint8Array.of(crc & 0xff, crc >>> 8);
    }
    default:
      throw new Error(`checksum inconnu '${algo as string}'`);
  }
}

/** Valeurs par défaut de tous les paramètres d'un message. */
export function defaultsFor(msg: MessageDef): ParamValues {
  const vals: ParamValues = {};
  for (const [name, pdef] of Object.entries(msg.params ?? {})) {
    if (pdef.default !== undefined) vals[name] = pdef.default;
    else if (String(pdef.type).toLowerCase() === 'enum') vals[name] = Object.keys(pdef.choices ?? {})[0] ?? 0;
    else if (['hex', 'raw', 'ascii'].includes(String(pdef.type).toLowerCase())) vals[name] = '';
    else vals[name] = 0;
  }
  return vals;
}

/**
 * Assemble la trame d'un message.
 *
 * Chaque morceau de msg.frame est :
 *   'AA 55'  des octets fixes en hexa
 *   '{led}'  un paramètre, remplacé par sa valeur encodée
 *   '{cs}'   le checksum, calculé une fois tous les autres octets connus
 *
 * Les valeurs absentes de `values` prennent leur valeur par défaut.
 * Lève une erreur lisible si une valeur est invalide.
 */
export function buildFrame(msg: MessageDef, values: ParamValues = {}): Uint8Array {
  const vals = { ...defaultsFor(msg), ...values };
  const parts: number[] = [];
  let csPos: number | null = null;   // position où insérer le checksum
  for (const raw of msg.frame) {
    const tok = raw.trim();
    if (tok.startsWith('{') && tok.endsWith('}')) {
      const name = tok.slice(1, -1);
      if (name === 'cs') {
        csPos = parts.length;
        continue;
      }
      const pdef = msg.params?.[name];
      if (!pdef) throw new Error(`paramètre '${name}' non défini`);
      parts.push(...encodeParam(name, pdef, vals[name] ?? ''));
    } else {
      parts.push(...parseHex(tok));
    }
  }
  if (csPos !== null) {
    // Calcul sur les octets de `start` (inclus) jusqu'au checksum (exclu).
    // Ex. start = 2 pour exclure l'en-tête AA 55.
    const { algo = 'xor8', start = 0 } = msg.checksum ?? {};
    const cs = checksum(algo, Uint8Array.from(parts.slice(start, csPos)));
    parts.splice(csPos, 0, ...cs);
  }
  return Uint8Array.from(parts);
}

/** Uint8Array -> 'AA 55 01' */
export function toHex(data: Uint8Array): string {
  return Array.from(data, (b) => b.toString(16).toUpperCase().padStart(2, '0')).join(' ');
}

/** Uint8Array -> texte imprimable, '.' pour les octets non affichables */
export function toAscii(data: Uint8Array): string {
  return Array.from(data, (b) => (b >= 32 && b < 127 ? String.fromCharCode(b) : '.')).join('');
}
