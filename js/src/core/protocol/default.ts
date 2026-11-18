/**
 * core/protocol/default.ts — Protocole générique intégré (identique à core/protocol/default.py
 * et à protocols/exemple_generique.json) : repli quand aucun fichier de protocole n'est fourni.
 *
 *   Requête : SYNC A5 5A | SEQ | CMD (2) | LEN | HCRC | DATA | DCRC (2, si DATA)
 *   Réponse : SYNC A5 5A | SEQ | STATUS | LEN | HCRC | DATA | DCRC (2, si DATA)
 */
import { Protocol } from './protocol';

const HCRC = { name: 'HCRC', size: 1, role: 'crc', algo: 'crc8', over: ['SYNC', 'LEN'], color: 'crc' };
const DATA = { name: 'DATA', role: 'data' };
const DCRC = { name: 'DCRC', size: 2, role: 'crc', algo: 'crc16_ccitt_false', over: ['DATA', 'DATA'], if: 'DATA', color: 'crc' };

export const GENERIC = {
  name: 'Exemple générique',
  description: "SYNC A5 5A, SEQ, CMD 16 bits, LEN, CRC8 d'en-tête, DATA, CRC16 CCITT des données, big endian",
  description_en: 'SYNC A5 5A, SEQ, 16-bit CMD, LEN, header CRC8, DATA, data CRC16 CCITT, big endian',
  byte_order: 'big',
  tx: [
    { name: 'SYNC', size: 2, role: 'value', value: '0xA55A', color: 'hdr' },
    { name: 'SEQ', size: 1, role: 'request_id', color: 'hdr' },
    { name: 'CMD', size: 2, role: 'command_id', color: 'cmd' },
    { name: 'LEN', size: 1, role: 'length', of: 'DATA' },
    HCRC, DATA, DCRC,
  ],
  rx: [
    { name: 'SYNC', size: 2, role: 'value', value: '0xA55A', color: 'hdr' },
    { name: 'SEQ', size: 1, role: 'request_id', color: 'hdr' },
    { name: 'STATUS', size: 1, role: 'error' },
    { name: 'LEN', size: 1, role: 'length', of: 'DATA' },
    HCRC, DATA, DCRC,
  ],
  errors: {
    '0': { fr: 'OK', en: 'OK' },
    '1': { fr: 'Commande inconnue', en: 'Unknown command' },
    '2': { fr: 'Paramètre invalide', en: 'Invalid parameter' },
    '3': { fr: 'CRC invalide', en: 'Invalid CRC' },
  },
};

export const DEFAULT_PROTOCOL = new Protocol(GENERIC);
