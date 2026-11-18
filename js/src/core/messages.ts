/**
 * core/messages.ts — Lecture des fichiers Msg_<nom>.json (ancien préfixe Message_ accepté).
 *
 * Portage de core/messages.py : valide les fichiers, déduit le groupe du nom
 * de fichier (Msg_Sorties.json -> 'Sorties') et fusionne les messages.
 *
 * Ce module ne lit pas le disque lui-même (il doit aussi fonctionner dans le
 * renderer, qui n'a pas accès au disque) : on lui passe le contenu déjà lu
 * (par le process principal Electron, un import statique, un fetch...).
 */
import { buildFrame } from './frames';
import type { MessageDef } from './types';
import { parseJsonc } from './jsonc';

export const MSG_PREFIX = 'Msg_';
/** Préfixes acceptés : le nouveau, puis l'ancien (fichiers existants). */
export const MSG_PREFIXES = [MSG_PREFIX, 'Message_'];

function prefixOf(name: string): string | undefined {
  return MSG_PREFIXES.find((p) => name.startsWith(p));
}

export interface RawMessageFile {
  /** Nom du fichier, ex. 'Msg_Sorties.json' : sert de groupe par défaut. */
  fileName: string;
  /** Contenu JSON (objet déjà parsé ou texte). */
  content: unknown;
}

export interface LoadResult {
  messages: MessageDef[];
  errors: { fileName: string; error: string }[];
}

/** 'Msg_Sorties.json' -> 'Sorties' */
export function groupFromFileName(fileName: string): string | undefined {
  const base = fileName.split(/[\\/]/).pop() ?? fileName;
  const stem = base.replace(/\.[^.]*$/, '');
  const prefix = prefixOf(stem);
  return prefix ? stem.slice(prefix.length) : undefined;
}

export function isMessageFileName(fileName: string): boolean {
  const base = fileName.split(/[\\/]/).pop() ?? fileName;
  return prefixOf(base) !== undefined && base.toLowerCase().endsWith('.json');
}

/** Valide un fichier de messages. Lève une erreur lisible si invalide. */
export function parseMessageFile(content: unknown, fileName = ''): MessageDef[] {
  const data = typeof content === 'string' ? parseJsonc(content) : content;
  let msgs: MessageDef[];
  if (Array.isArray(data)) msgs = data;
  else if (data && typeof data === 'object' && Array.isArray((data as { messages?: unknown }).messages))
    msgs = (data as { messages: MessageDef[] }).messages;
  else if (data && typeof data === 'object' && 'frame' in data) msgs = [data as MessageDef];
  // Fichier ne contenant que des commandes du protocole et / ou des codes
  // d'erreur (lus par core/commands.py côté Python) : pas de message ici.
  else if (data && typeof data === 'object' && ('commands' in data || 'errors' in data)) msgs = [];
  else throw new Error('format JSON non reconnu');

  const fileGroup =
    (!Array.isArray(data) && (data as { group?: string }).group) || groupFromFileName(fileName);
  // Protocole pour lequel le fichier a été écrit (information recopiée dans chaque message)
  const fileProtocol = Array.isArray(data) ? undefined : (data as { protocol?: string | string[] }).protocol;

  return msgs.map((m) => {
    // Chaque message reçoit le groupe du fichier, sauf s'il précise le sien
    const isRequest = !!m && typeof m.request === 'object' && m.request !== null;
    if (!m || typeof m.name !== 'string' || (!Array.isArray(m.frame) && !isRequest))
      throw new Error("chaque message doit avoir 'name' et 'frame'");
    const msg: MessageDef = fileGroup && !m.group ? { ...m, group: fileGroup } : { ...m };
    if (fileProtocol && !msg.protocol) msg.protocol = fileProtocol;
    if (isRequest) {
      // Message de protocole : la trame se construit avec le protocole en cours
      // (Protocol.build), pas avec buildFrame ; on vérifie seulement COMMAND ID.
      if (msg.request!.command_id === undefined)
        throw new Error(`message '${m.name}' : 'request' : 'command_id' manquant`);
      if (!Array.isArray(msg.frame)) msg.frame = [];
      return msg;
    }
    try {
      // On construit la trame avec les valeurs par défaut : une erreur de
      // définition (paramètre manquant, hexa invalide...) est détectée dès
      // le chargement plutôt qu'au premier envoi.
      buildFrame(msg);
    } catch (e) {
      throw new Error(`message '${m.name}' : ${(e as Error).message}`);
    }
    return msg;
  });
}

/** Charge plusieurs fichiers ; un fichier invalide n'empêche pas les autres de charger. */
export function loadMessageFiles(files: RawMessageFile[]): LoadResult {
  const sorted = [...files].sort((a, b) => a.fileName.toLowerCase().localeCompare(b.fileName.toLowerCase()));
  const result: LoadResult = { messages: [], errors: [] };
  for (const f of sorted) {
    try {
      result.messages.push(...parseMessageFile(f.content, f.fileName));
    } catch (e) {
      result.errors.push({ fileName: f.fileName, error: (e as Error).message });
    }
  }
  return result;
}

/** Regroupe les messages par groupe, dans l'ordre d'apparition. */
export function groupMessages(messages: MessageDef[]): { group: string; messages: MessageDef[] }[] {
  const map = new Map<string, MessageDef[]>();
  for (const m of messages) {
    const g = m.group ?? '';
    if (!map.has(g)) map.set(g, []);
    map.get(g)!.push(m);
  }
  return [...map].map(([group, msgs]) => ({ group, messages: msgs }));
}
