/**
 * core/protocol/encoding.ts — Codage de la trame sur la ligne (portage de encoding.py).
 *
 * "encoding": {"type": "ascii_hex", "start": ":", "end": "\r\n"} : chaque octet est écrit en
 * deux caractères hexa ASCII entre un début et une fin (Modbus ASCII).
 */
import { ProtocolError } from './common';

const latin1 = (text: string) => Uint8Array.from(text, (c) => c.charCodeAt(0) & 0xff);

/** Délimiteur lisible comme repr() de Python : ':' , '\r\n'. */
function show(delimiter: Uint8Array): string {
  const text = Array.from(delimiter, (b) => {
    if (b === 13) return '\\r';
    if (b === 10) return '\\n';
    if (b === 9) return '\\t';
    return String.fromCharCode(b);
  }).join('');
  return `'${text}'`;
}

function startsWith(data: Uint8Array, prefix: Uint8Array): boolean {
  return prefix.length <= data.length && prefix.every((b, i) => data[i] === b);
}

function indexOf(data: Uint8Array, needle: Uint8Array): number {
  for (let i = 0; i + needle.length <= data.length; i++) {
    if (needle.every((b, j) => data[i + j] === b)) return i;
  }
  return -1;
}

/** Le plus long début fait de paires hexa -> [octets, reste invalide ?]. */
function hexPrefix(text: Uint8Array): [Uint8Array, boolean] {
  const out: number[] = [];
  for (let i = 0; i + 1 < text.length; i += 2) {
    const pair = String.fromCharCode(text[i], text[i + 1]);
    if (!/^[0-9A-Fa-f]{2}$/.test(pair)) return [Uint8Array.from(out), true];
    out.push(parseInt(pair, 16));
  }
  return [Uint8Array.from(out), text.length % 2 === 1];
}

export class AsciiHex {
  readonly start: Uint8Array;
  readonly end: Uint8Array;

  constructor(start = ':', end = '\r\n', readonly lowercase = false) {
    this.start = latin1(start);
    this.end = latin1(end);
  }

  wrap(binary: Uint8Array): Uint8Array {
    let text = Array.from(binary, (b) => b.toString(16).padStart(2, '0')).join('');
    text = this.lowercase ? text.toLowerCase() : text.toUpperCase();
    const body = latin1(text);
    const out = new Uint8Array(this.start.length + body.length + this.end.length);
    out.set(this.start, 0);
    out.set(body, this.start.length);
    out.set(this.end, this.start.length + body.length);
    return out;
  }

  /** Octets reçus -> [trame binaire, problèmes, fin trouvée, octets après la fin]. */
  unwrap(raw: Uint8Array): [Uint8Array, string[], boolean, Uint8Array] {
    if (!startsWith(raw, this.start)) return [new Uint8Array(), [`début de trame ${show(this.start)} absent`], false, new Uint8Array()];
    const body = raw.slice(this.start.length);
    const index = this.end.length ? indexOf(body, this.end) : -1;
    const complete = index >= 0 || !this.end.length;
    const hexPart = index >= 0 ? body.slice(0, index) : body;
    const extra = index >= 0 ? body.slice(index + this.end.length) : new Uint8Array();
    const problems: string[] = [];
    if (!complete) problems.push(`fin de trame ${show(this.end)} absente`);
    const [binary, bad] = hexPrefix(hexPart);
    if (bad) problems.push('caractères hexa ASCII invalides');
    return [binary, problems, complete, extra];
  }

  /** Début d'une trame reçue -> [bon début ?, octets binaires déjà lisibles]. */
  prefix(raw: Uint8Array): [boolean, Uint8Array] {
    if (!startsWith(raw, this.start)) return [startsWith(this.start, raw), new Uint8Array()];
    return [true, hexPrefix(raw.slice(this.start.length))[0]];
  }

  /** Couleurs de la trame binaire -> couleurs des octets envoyés (2 caractères par octet). */
  rawSegments(segments: [number, number, string][], binaryLength: number): [number, number, string][] {
    const offset = this.start.length;
    const out: [number, number, string][] = offset ? [[0, offset, 'hdr']] : [];
    for (const [start, length, tag] of segments) out.push([offset + 2 * start, 2 * length, tag]);
    if (this.end.length) out.push([offset + 2 * binaryLength, this.end.length, 'hdr']);
    return out;
  }
}

/** Section "encoding" -> codage, ou undefined (binaire). */
export function parseEncoding(conf: Record<string, unknown>): AsciiHex | undefined {
  let spec = conf.encoding as unknown;
  if (spec === undefined || spec === null || spec === 'binary') return undefined;
  if (typeof spec === 'string') spec = { type: spec };
  const s = spec as Record<string, unknown>;
  if (typeof s === 'object' && (s.type ?? 'binary') === 'binary') return undefined;
  if (typeof s !== 'object' || s.type !== 'ascii_hex') throw new ProtocolError('encoding : type inconnu (binary ou ascii_hex)');
  return new AsciiHex(String(s.start ?? ':'), String(s.end ?? '\r\n'), Boolean(s.lowercase));
}
