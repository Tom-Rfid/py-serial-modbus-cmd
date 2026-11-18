import { readdirSync, readFileSync } from 'node:fs';
import { describe, expect, it } from 'vitest';

import { groupFromFileName, groupMessages, loadMessageFiles, parseMessageFile } from '../src/core/messages';

const dir = new URL('../../tests/data/messages/', import.meta.url); // messages d'essai, communs à toutes les versions
const files = readdirSync(dir, { withFileTypes: true })
  .filter((e) => e.isFile())
  .map((e) => ({ fileName: e.name, content: readFileSync(new URL(e.name, dir), 'utf-8') }));

describe('fichiers de messages', () => {
  it("charge les Msg_*.json d'essai", () => {
    const { messages, errors } = loadMessageFiles(files);
    expect(errors).toEqual([]);
    expect(messages).toHaveLength(7);
    expect(groupMessages(messages).map((g) => g.group)).toEqual(['Divers', 'Modbus', 'Sorties', 'Système']);
  });

  it('déduit le groupe du nom de fichier', () => {
    expect(groupFromFileName('Msg_Moteur.json')).toBe('Moteur');
    expect(groupFromFileName('Message_Moteur.json')).toBe('Moteur');      // ancien préfixe
    expect(groupFromFileName('C:\\x\\Msg_A.json')).toBe('A');
    expect(groupFromFileName('autre.json')).toBeUndefined();
    const [m] = parseMessageFile({ messages: [{ name: 'X', frame: ['01'] }] }, 'Msg_Moteur.json');
    expect(m.group).toBe('Moteur');
  });

  it("isole un fichier invalide sans bloquer les autres", () => {
    const res = loadMessageFiles([
      { fileName: 'Msg_Bon.json', content: { messages: [{ name: 'ok', frame: ['01'] }] } },
      { fileName: 'Msg_Mauvais.json', content: { messages: [{ name: 'ko', frame: ['{inconnu}'] }] } },
    ]);
    expect(res.messages.map((m) => m.name)).toEqual(['ok']);
    expect(res.errors[0].fileName).toBe('Msg_Mauvais.json');
    expect(res.errors[0].error).toContain("'inconnu'");
  });

  it('recopie la clé "protocol" du fichier dans chaque message', () => {
    const [m] = parseMessageFile({ protocol: 'Modbus RTU', messages: [{ name: 'X', frame: ['01'] }] }, 'Msg_A.json');
    expect(m.protocol).toBe('Modbus RTU');
    const [n] = parseMessageFile({ protocol: 'Modbus RTU', messages: [{ name: 'Y', frame: ['01'], protocol: 'Autre' }] });
    expect(n.protocol).toBe('Autre');
  });
});
