/** Contrat avec la version Python : mêmes résultats pour tests/protocol_vectors.json. */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import { parseHex, toHex } from '../src/core/frames';
import {
  CRC_PRESETS, DEFAULT_PROTOCOL, Protocol, ProtocolError, QUERY, RESPONSE, parseProtocol, protocolSegments,
  type FrameKind,
} from '../src/core/protocol';

const V = JSON.parse(readFileSync(new URL('../../tests/protocol_vectors.json', import.meta.url), 'utf-8'));
const KINDS: Record<string, FrameKind> = { tx: QUERY, rx: RESPONSE };
const bytes = (hex: string) => parseHex(hex);
const ascii = (s: string) => new TextEncoder().encode(s);

describe('CRC : valeurs de contrôle partagées', () => {
  it.each(Object.entries(V.crc_check as Record<string, number>))('%s', (name, value) => {
    expect(CRC_PRESETS[name].compute(ascii('123456789'))).toBe(value);
  });
});

describe.each((V.protocols as any[]).map((p) => [p.name, p] as const))('protocole %s', (_name, c) => {
  const p = new Protocol(c.conf);

  it('construction', () => {
    for (const b of c.build) {
      const run = () => p.build(KINDS[b.kind], bytes(b.data), b.values, b.variant ?? undefined);
      if (b.error) expect(run, JSON.stringify(b)).toThrow();
      else expect(toHex(run()), JSON.stringify(b)).toBe(b.frame);
    }
  });

  it('décodage (champs, contrôles, erreurs, couleurs)', () => {
    for (const e of c.decode) {
      const d = p.decode(bytes(e.frame), KINDS[e.kind]);
      const got = {
        complete: d.complete, ok: d.ok, errors: d.errors, extra: toHex(d.extra), variant: d.variant,
        fields: d.fields.map((f) => ({
          name: f.name, start: f.start, raw: toHex(f.raw), value: f.value ?? null,
          ok: f.ok ?? null, note: f.note, role: f.role, meaning: f.meaning ?? '',
        })),
        segments: protocolSegments(d),
      };
      const want = {
        complete: e.complete, ok: e.ok, errors: e.errors, extra: e.extra, variant: e.variant, fields: e.fields, segments: e.segments,
      };
      expect(got, e.frame).toEqual(want);
    }
  });

  it('appartenance et CRC principal', () => {
    for (const m of c.matches) expect(p.matches(bytes(m.frame), KINDS[m.kind]), m.frame).toBe(m.result);
    expect(toHex(p.crcBytes(bytes('01 03 00 00 00 0A')))).toBe(c.main_crc);
    expect(p.maxValue(QUERY, 'request_id') ?? null).toBe(c.max_request_id);
  });
});

describe('fichiers de conf invalides : mêmes messages que Python', () => {
  it.each((V.invalid as any[]).map((c) => [c.message, c] as const))('%s', (message, c) => {
    expect(() => new Protocol(c.conf)).toThrow(ProtocolError);
    expect(() => new Protocol(c.conf)).toThrow(message);
  });
});

describe('utilisation', () => {
  it('protocole générique intégré', () => {
    const f = DEFAULT_PROTOCOL.buildQuery(5, 4, Uint8Array.of(1));
    const d = DEFAULT_PROTOCOL.decode(f, QUERY);
    expect([d.ok, d.requestId, d.commandId, toHex(d.data!.raw), d.crcOk]).toEqual([true, 5, 4, '01', true]);
    expect(DEFAULT_PROTOCOL.decode(DEFAULT_PROTOCOL.buildResponse(5, 4), RESPONSE).error).toBe(4);
    expect(toHex(DEFAULT_PROTOCOL.buildQuery(1, 7, Uint8Array.of(1, 2, 3)))).toBe('A5 5A 01 00 07 03 09 01 02 03 AD AD');
  });
  it('Modbus ASCII : codage, décodage et couleurs sur la ligne', () => {
    const p = new Protocol({
      name: 'ascii', byte_order: 'big', encoding: { type: 'ascii_hex', start: ':', end: '\r\n' },
      tx: [{ name: 'ADR', size: 1, role: 'request_id', color: 'hdr' }, { name: 'FC', size: 1, role: 'command_id', color: 'cmd' },
        { name: 'DATA', role: 'data' }, { name: 'LRC', size: 1, role: 'crc', algo: 'sum8_2c', over: ['ADR', 'DATA'], color: 'crc' }],
      rx: [{ name: 'DATA', role: 'data' }],
    });
    const frame = p.buildQuery(1, 3, bytes('00 00 00 0A'));
    expect(new TextDecoder().decode(frame)).toBe(':01030000000AF2\r\n');
    const d = p.decode(frame, QUERY);
    expect([d.ok, d.requestId, d.commandId, toHex(d.binary)]).toEqual([true, 1, 3, '01 03 00 00 00 0A F2']);
    expect(p.displaySegments(d, protocolSegments(d))).toEqual([[0, 1, 'hdr'], [1, 2, 'hdr'], [3, 2, 'cmd'], [13, 2, 'crc'], [15, 2, 'hdr']]);
    expect(p.decode(ascii(':0103'), QUERY).errors[0]).toBe("fin de trame '\\r\\n' absente");
    expect(p.matches(ascii(':01'), QUERY)).toBe(true);
    expect(p.matches(ascii('01'), QUERY)).toBe(false);
    expect(toHex(p.frameEnd!)).toBe('0D 0A');
  });
  it('parseProtocol lit un texte JSON et préfixe les erreurs du nom de fichier', () => {
    expect(parseProtocol(readFileSync(new URL('../../tests/data/protocols/exemple_generique.json', import.meta.url), 'utf-8')).name).toBe('Exemple générique');
    expect(() => parseProtocol('{"tx": []}', 'x.json')).toThrow('x.json : "tx" : liste de champs attendue');
    expect(() => parseProtocol('{', 'x.json')).toThrow('JSON invalide');
  });
});

describe('JSON avec commentaires', () => {
  it('commentaires // et /* */ ignorés, chaînes gardées', () => {
    const text = '{ // c\n "name": "http://x//y", /* b\n c */ "description": "q\\"//" ,\n "tx": [{"name": "D", "role": "data"}], "rx": [{"name": "D", "role": "data"}] }';
    const p = parseProtocol(text);
    expect([p.name, p.description]).toEqual(['http://x//y', 'q"//']);
  });
});
