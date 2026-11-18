/** Canaux IPC partagés entre le process principal et le preload. */
export const CHANNELS = {
  list: 'serialhex:list',
  check: 'serialhex:check',
  open: 'serialhex:open',
  reconfigure: 'serialhex:reconfigure',
  close: 'serialhex:close',
  write: 'serialhex:write',
  signals: 'serialhex:signals',
  readMessages: 'serialhex:read-messages',
  readProtocols: 'serialhex:read-protocols',
  // main -> renderer
  data: 'serialhex:data',
  closed: 'serialhex:closed',
} as const;

/** Réponse des handlers : les erreurs passent en clair, sans le préfixe ajouté par Electron. */
export type IpcResult<T> = { ok: true; value: T } | { ok: false; error: string };
