/**
 * electron/preload.ts — Côté preload Electron.
 *
 * Le preload fait le lien entre le renderer (React, sans accès au système)
 * et le process principal. Il expose `window.serialhex`, un objet dont chaque
 * méthode envoie une demande IPC au process principal.
 *
 * contextBridge garantit que le renderer ne reçoit que ces fonctions,
 * jamais ipcRenderer lui-même (sécurité Electron).
 *
 *   // preload.ts de l'application
 *   import { exposeSerialHex } from 'serialhex/electron/preload';
 *   exposeSerialHex();
 *
 * `window.serialhex` implémente SerialTransport : il se passe tel quel à `new SerialLink(...)`.
 */
import { contextBridge, ipcRenderer, type IpcRenderer } from 'electron';

import type { RawMessageFile } from '../core/messages';
import type { SerialTransport } from '../link/types';
import { CHANNELS, type IpcResult } from './channels';

/** Ce que le renderer trouve dans window.serialhex. */
export interface SerialHexBridge extends SerialTransport {
  /** Contenu des Msg_*.json du dossier configuré côté main (messagesDir). */
  readMessageFiles(): Promise<RawMessageFile[]>;
  /** Contenu des fichiers de protocole du dossier configuré côté main (protocolsDir) : à passer à parseProtocol. */
  readProtocolFiles(): Promise<RawMessageFile[]>;
}

/**
 * Construit le pont à partir d'ipcRenderer. Séparé de exposeSerialHex pour
 * pouvoir être testé avec un faux ipcRenderer.
 */
export function createSerialHexBridge(ipc: Pick<IpcRenderer, 'invoke' | 'on' | 'removeListener'>): SerialHexBridge {
  // Appelle un canal et déballe la réponse { ok, value | error } du process principal
  const call = async <T>(channel: string, ...args: unknown[]): Promise<T> => {
    const res = (await ipc.invoke(channel, ...args)) as IpcResult<T>;
    if (!res.ok) throw new Error(res.error);
    return res.value;
  };

  // S'abonne à un événement du process principal ; retourne la fonction de désabonnement.
  // L'objet `event` d'Electron n'est pas transmis au renderer.
  const listen = <T>(channel: string, listener: (payload: T) => void) => {
    const wrapped = (_event: unknown, payload: T) => listener(payload);
    ipc.on(channel, wrapped);
    return () => {
      ipc.removeListener(channel, wrapped);
    };
  };

  return {
    listPorts: () => call(CHANNELS.list),
    checkPort: (path) => call(CHANNELS.check, path),
    open: (config) => call(CHANNELS.open, config),
    reconfigure: (format) => call(CHANNELS.reconfigure, format),
    close: () => call(CHANNELS.close),
    write: (data) => call(CHANNELS.write, data),
    setSignals: (signals) => call(CHANNELS.signals, signals),
    readMessageFiles: () => call(CHANNELS.readMessages),
    readProtocolFiles: () => call(CHANNELS.readProtocols),
    onData: (listener) => listen<Uint8Array>(CHANNELS.data, (d) => listener(new Uint8Array(d))),
    onClose: (listener) => listen<string>(CHANNELS.closed, listener),
  };
}

/** À appeler dans le preload de l'application : crée window.serialhex (ou window[key]). */
export function exposeSerialHex(key = 'serialhex'): void {
  contextBridge.exposeInMainWorld(key, createSerialHexBridge(ipcRenderer));
}
