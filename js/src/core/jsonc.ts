/**
 * core/jsonc.ts — JSON avec commentaires (portage de core/jsonc.py).
 *
 * Les fichiers de protocole et de commandes peuvent contenir des commentaires // et /* *\/,
 * comme dans VS Code. Ils sont remplacés par des espaces avant JSON.parse : les positions
 * des messages d'erreur restent justes. Un « // » dans une chaîne ("http://...") est gardé.
 */

/** Texte JSON sans ses commentaires // et /* *\/ (remplacés par des espaces). */
export function stripJsonComments(text: string): string {
  let out = '';
  let i = 0;
  let inString = false;
  while (i < text.length) {
    const c = text[i];
    if (inString) {
      out += c;
      if (c === '\\' && i + 1 < text.length) {
        out += text[i + 1]; // caractère échappé : \" ne ferme pas la chaîne
        i += 2;
        continue;
      }
      if (c === '"') inString = false;
      i += 1;
    } else if (c === '"') {
      inString = true;
      out += c;
      i += 1;
    } else if (text.startsWith('//', i)) {
      let end = text.indexOf('\n', i);
      if (end < 0) end = text.length;
      out += ' '.repeat(end - i);
      i = end;
    } else if (text.startsWith('/*', i)) {
      let end = text.indexOf('*/', i + 2);
      end = end < 0 ? text.length : end + 2;
      out += text.slice(i, end).replace(/[^\n]/g, ' ');
      i = end;
    } else {
      out += c;
      i += 1;
    }
  }
  return out;
}

/** JSON.parse acceptant les commentaires (et un BOM en tête). */
export function parseJsonc(text: string): unknown {
  return JSON.parse(stripJsonComments(text.replace(/^﻿/, '')));
}
