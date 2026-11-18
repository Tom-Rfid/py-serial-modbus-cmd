/**
 * core/protocol/colors.ts — Couleurs d'une trame décodée (comme color_segments en Python).
 *
 * Tag : couleur du fichier (hdr, cmd, crc, na), 'err' pour un octet fixe ou un CRC faux,
 * 'perr_ok' / 'perr_ko' pour le code d'erreur à 0 / non nul. Rien si la trame est incomplète.
 */
import type { Decoded, DecodedField } from './decoded';

export function protocolSegments(d: Decoded): [number, number, string][] {
  if (!d.complete) return [];
  const out: [number, number, string][] = [];
  for (const f of d.fields) {
    const tag = tagOf(f);
    if (f.raw.length && tag) out.push([f.start, f.raw.length, tag]);
  }
  return out;
}

function tagOf(f: DecodedField): string | undefined {
  if (f.role === 'error') return f.value === 0 ? 'perr_ok' : 'perr_ko';
  if (f.ok === false) return 'err';
  return f.color;
}
