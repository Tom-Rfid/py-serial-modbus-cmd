/**
 * Côté renderer : récupère le pont exposé par le preload.
 *
 *   import { getSerialHexBridge } from 'serialhex';
 *   const link = new SerialLink(getSerialHexBridge());
 */
import type { SerialHexBridge } from './preload';

declare global {
  interface Window {
    serialhex?: SerialHexBridge;
  }
}

export function getSerialHexBridge(key = 'serialhex'): SerialHexBridge {
  const bridge = (globalThis as Record<string, unknown>)[key] as SerialHexBridge | undefined;
  if (!bridge) {
    throw new Error(
      `window.${key} introuvable : appeler exposeSerialHex() dans le preload ` +
        `et registerSerialHexIpc(ipcMain) dans le process principal.`,
    );
  }
  return bridge;
}

export type { SerialHexBridge };
