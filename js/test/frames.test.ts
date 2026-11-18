/** Contrat avec la version Python : mêmes trames pour tests/vectors.json. */
import { readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import { buildFrame, parseHex, parseIntValue, toAscii, toHex } from '../src/core/frames';
import type { MessageDef, ParamValues } from '../src/core/types';

interface Case { name: string; message: MessageDef; values: ParamValues; frame?: string; error?: boolean }
const vectors: { cases: Case[] } = JSON.parse(
  readFileSync(new URL('../../tests/vectors.json', import.meta.url), 'utf-8'),
);

describe('vecteurs partagés avec Python', () => {
  it.each(vectors.cases.map((c) => [c.name, c] as const))('%s', (_name, c) => {
    if (c.error) expect(() => buildFrame(c.message, c.values)).toThrow();
    else expect(toHex(buildFrame(c.message, c.values))).toBe(c.frame);
  });
});

describe('conversions', () => {
  it('parseIntValue suit int(s, 0) de Python', () => {
    expect(parseIntValue('0x1F')).toBe(31);
    expect(parseIntValue('0b101')).toBe(5);
    expect(parseIntValue('-0x10')).toBe(-16);
    expect(parseIntValue('1_000')).toBe(1000);
    expect(parseIntValue('010')).toBe(10);
    expect(() => parseIntValue('12a')).toThrow();
  });
  it('parseHex accepte plusieurs écritures', () => {
    expect(toHex(parseHex('AA 55'))).toBe('AA 55');
    expect(toHex(parseHex('aa55'))).toBe('AA 55');
    expect(toHex(parseHex('0xAA,0x55'))).toBe('AA 55');
    expect(() => parseHex('AA5')).toThrow();
  });
  it('toAscii masque les octets non imprimables', () => {
    expect(toAscii(Uint8Array.of(0x48, 0x00, 0x69))).toBe('H.i');
  });
});
