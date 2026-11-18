/**
 * core/protocol — Moteur de protocole configurable (portage de core/protocol/ en Python).
 *
 * La structure des trames requête (tx) et réponse (rx) vient d'un fichier de conf
 * (dossier protocols/ du projet Python ; options : docs/Francais/CONF_PROTOCOLE.md). Mêmes
 * résultats que Python, octet pour octet et message pour message (tests/protocol_vectors.json).
 *
 * Ce module ne lit pas le disque : on lui passe le contenu du fichier (objet ou texte JSON).
 *
 *   common.ts      QUERY, RESPONSE, ProtocolError, pack / unpack
 *   crc.ts         CRC 8 / 16 / 32 bits et sommes
 *   fields.ts      description d'un champ, vérifications du fichier ; placement.ts : at / atb / after
 *   bits.ts        champs en bits (LENb, atb, bit_order)
 *   decoded.ts     résultat d'un décodage
 *   encoding.ts    codage sur la ligne (Modbus ASCII : « :0103…\r\n »)
 *   builder.ts     construction ; decoder.ts : décodage
 *   protocol.ts    classe Protocol ; default.ts : protocole générique intégré ; colors.ts : couleurs
 */
import { parseJsonc } from '../jsonc';
import { ProtocolError } from './common';
import { Protocol } from './protocol';

export { ProtocolError, QUERY, RESPONSE, type ByteOrder, type FrameKind } from './common';
export { CRC_PRESETS, Crc, type CrcKind } from './crc';
export { Decoded, fieldSpan, type DecodedField } from './decoded';
export { ROLES, valueText, type FieldColor, type FieldRole, type FieldSpec, type Pos, type ValueText } from './fields';
export { type BuildValues } from './builder';
export { Protocol, type Segment, type Variant } from './protocol';
export { AsciiHex, parseEncoding } from './encoding';
export { DEFAULT_PROTOCOL, GENERIC } from './default';
export { protocolSegments } from './colors';
export { readBits, writeBits, type BitOrder } from './bits';

/** Lit le contenu d'un fichier de protocole (objet ou texte JSON). Lève ProtocolError. */
export function parseProtocol(content: unknown, fileName?: string): Protocol {
  const conf = typeof content === 'string' ? parseJson(content, fileName) : content;
  try {
    return new Protocol(conf as Record<string, unknown>, fileName);
  } catch (e) {
    if (e instanceof ProtocolError && fileName) throw new ProtocolError(`${fileName} : ${e.message}`);
    throw e;
  }
}

function parseJson(text: string, fileName?: string): unknown {
  try {
    return parseJsonc(text); // commentaires // et /* */ acceptés
  } catch (e) {
    throw new ProtocolError(`${fileName ?? 'protocole'} : JSON invalide : ${(e as Error).message}`);
  }
}
