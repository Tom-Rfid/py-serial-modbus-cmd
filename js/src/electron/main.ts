/**
 * electron/main.ts — Côté process principal Electron.
 *
 * Seul le process principal a accès au matériel et au disque. Ce module :
 *   - ouvre / ferme le port série avec le paquet `serialport`
 *   - répond aux demandes du renderer reçues par IPC (canaux 'serialhex:*')
 *   - renvoie au renderer les octets reçus et les pertes de connexion
 *   - lit les fichiers Msg_*.json du dossier `messagesDir`, et seulement celui-là
 *   - lit les fichiers de protocole (*.json) du dossier `protocolsDir`, et seulement celui-là
 *
 * Utilisation :
 *   // main.ts de l'application
 *   import { ipcMain } from 'electron';
 *   import { registerSerialHexIpc } from 'serialhex/electron/main';
 *   registerSerialHexIpc(ipcMain, {
 *     messagesDir: path.join(app.getAppPath(), 'msgLibrary', 'msgManual'),
 *     protocolsDir: path.join(app.getAppPath(), 'protocols'),
 *   });
 *
 * Un seul port ouvert à la fois. Il est fermé si la fenêtre qui l'a ouvert est détruite.
 */
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type { IpcMain, IpcMainInvokeEvent, WebContents } from 'electron';
import { SerialPort } from 'serialport';

import { isMessageFileName, type RawMessageFile } from '../core/messages';
import {
  withDefaults,
  type PortCheck, type PortInfo, type SerialConfig, type SerialFormat, type Signals,
} from '../link/types';
import { CHANNELS, type IpcResult } from './channels';
import { classifyOpenError } from './errors';

/** Options de registerSerialHexIpc. */
export interface SerialHexMainOptions {
  /** Dossier des Msg_*.json renvoyés au renderer (aucun autre dossier n'est lisible). */
  messagesDir?: string;
  /** Dossier des fichiers de protocole (*.json, ex. modbus_rtu.json) renvoyés au renderer. */
  protocolsDir?: string;
}

/** Fonction qui traite une demande du renderer (un canal IPC). */
type Handler = (event: IpcMainInvokeEvent, ...args: any[]) => Promise<unknown>;

/**
 * Enregistre les handlers IPC. À appeler une fois au démarrage, avant de créer la fenêtre.
 * Retourne une fonction qui retire les handlers et ferme le port.
 */
export function registerSerialHexIpc(ipcMain: IpcMain, options: SerialHexMainOptions = {}): () => void {
  let port: SerialPort | null = null;                       // port ouvert
  let config: Required<SerialConfig> | null = null;         // ses réglages
  let owner: WebContents | null = null;                     // fenêtre qui l'a ouvert (destinataire des événements)

  /** Envoie un événement à la fenêtre propriétaire, si elle existe encore. */
  const send = (channel: string, payload: unknown) => {
    if (owner && !owner.isDestroyed()) owner.send(channel, payload);
  };

  /**
   * Oublie le port courant et retire ses écouteurs, AVANT de le fermer :
   * ainsi la fermeture volontaire n'est pas signalée comme une perte de connexion.
   */
  const detach = () => {
    const p = port;
    port = null;
    config = null;
    p?.removeAllListeners();
    return p;
  };

  /** Ferme le port courant (fermeture volontaire, rien n'est signalé au renderer). */
  const closePort = async () => {
    const p = detach();
    if (p?.isOpen) await new Promise<void>((resolve) => p.close(() => resolve()));
  };

  /** Mémorise le port ouvert et branche ses événements vers la fenêtre `wc`. */
  const attach = (p: SerialPort, cfg: Required<SerialConfig>, wc: WebContents) => {
    port = p;
    config = cfg;
    if (owner !== wc) {
      owner = wc;
      // Fenêtre fermée : on ferme le port, personne ne l'utilise plus
      wc.once('destroyed', () => {
        if (owner === wc) {
          owner = null;
          void closePort();
        }
      });
    }
    // Octets reçus : transmis bruts, le découpage en trames est fait côté renderer
    p.on('data', (chunk: Buffer) => send(CHANNELS.data, new Uint8Array(chunk)));
    // Fermeture ou erreur non demandée (câble retiré...) : signalée une seule fois
    const lost = (reason: string) => {
      if (port !== p) return;          // fermeture volontaire ou déjà signalée
      detach();
      send(CHANNELS.closed, reason);
    };
    p.on('close', (err?: Error & { disconnected?: boolean }) => lost(err?.message || 'port fermé'));
    p.on('error', (err: Error) => lost(err.message));
  };

  // Un handler par canal IPC (voir docs/Francais/INTERFACE.md pour le protocole)
  const handlers: Record<string, Handler> = {
    [CHANNELS.list]: async () => listPorts(),

    [CHANNELS.check]: async (_e, p: string) =>
      port && config?.path === p
        ? ({ status: 'busy', message: 'connecté (utilisé par cette application)' } satisfies PortCheck)
        : checkPort(p),

    [CHANNELS.open]: async (e, cfg: SerialConfig) => {
      await closePort();
      const full = withDefaults(cfg) as Required<SerialConfig>;
      const p = await openPort(full);
      attach(p, full, e.sender);
    },

    // Seule la vitesse peut changer port ouvert (port.update) ; pour les autres
    // réglages, serialport impose de fermer puis rouvrir le port.
    [CHANNELS.reconfigure]: async (e, fmt: Partial<SerialFormat>) => {
      if (!port || !config) throw new Error('port non connecté');
      const next = { ...config, ...fmt } as Required<SerialConfig>;
      const onlyBaud = Object.keys(fmt).every((k) => k === 'baudRate' || fmt[k as keyof SerialFormat] === undefined
        || fmt[k as keyof SerialFormat] === config![k as keyof SerialFormat]);
      if (onlyBaud) {
        const p = port;
        await new Promise<void>((res, rej) => p.update({ baudRate: next.baudRate }, (err) => (err ? rej(err) : res())));
        config = next;
        return;
      }
      // Les autres réglages imposent de rouvrir le port
      await closePort();
      const p = await openPort(next);
      attach(p, next, e.sender);
    },

    [CHANNELS.close]: async () => closePort(),

    // Résolu une fois les octets réellement transmis (drain), pas seulement mis en file
    [CHANNELS.write]: async (_e, data: Uint8Array) => {
      const p = port;
      if (!p) throw new Error('port non connecté');
      await new Promise<void>((res, rej) => {
        p.write(Buffer.from(data), (err) => {
          if (err) return rej(err);
          p.drain((err2) => (err2 ? rej(err2) : res()));
        });
      });
    },

    [CHANNELS.signals]: async (_e, s: Signals) => {
      const p = port;
      if (!p) throw new Error('port non connecté');
      const flags: { dtr?: boolean; rts?: boolean } = {};
      if (s.dtr !== undefined) flags.dtr = s.dtr;
      if (s.rts !== undefined) flags.rts = s.rts;
      await new Promise<void>((res, rej) => p.set(flags, (err) => (err ? rej(err) : res())));
    },

    [CHANNELS.readMessages]: async () => readMessageFiles(options.messagesDir),

    [CHANNELS.readProtocols]: async () => readProtocolFiles(options.protocolsDir),
  };

  // Enregistrement des handlers. Chaque réponse est enveloppée dans
  // { ok, value } / { ok: false, error } : sans cela, Electron ajouterait
  // « Error invoking remote method... » devant chaque message d'erreur.
  for (const [channel, fn] of Object.entries(handlers)) {
    ipcMain.handle(channel, async (event, ...args): Promise<IpcResult<unknown>> => {
      try {
        return { ok: true, value: await fn(event, ...args) };
      } catch (err) {
        return { ok: false, error: err instanceof Error ? err.message : String(err) };
      }
    });
  }

  return () => {
    for (const channel of Object.keys(handlers)) ipcMain.removeHandler(channel);
    void closePort();
  };
}

// ----------------------------------------------------------------------
// Fonctions utilitaires (utilisables aussi sans IPC)
// ----------------------------------------------------------------------

/** Ports présents, triés naturellement (COM3 avant COM10). N'ouvre aucun port. */
export async function listPorts(): Promise<PortInfo[]> {
  const ports = await SerialPort.list();
  return ports
    .map((p) => {
      const friendly = (p as { friendlyName?: string }).friendlyName;
      return {
        path: p.path,
        // Windows : 'USB-SERIAL CH340 (COM3)' -> 'USB-SERIAL CH340'
        description: (friendly ?? p.manufacturer ?? '').replace(/\s*\((COM\d+)\)$/i, ''),
        manufacturer: p.manufacturer,
        vendorId: p.vendorId,
        productId: p.productId,
        serialNumber: p.serialNumber,
      };
    })
    .sort((a, b) => a.path.localeCompare(b.path, undefined, { numeric: true }));
}

/** Ouvre un port. Rejette avec un message lisible (« COM3 déjà utilisé... »). */
export function openPort(cfg: Required<SerialConfig>): Promise<SerialPort> {
  return new Promise((resolve, reject) => {
    const p = new SerialPort({
      path: cfg.path,
      baudRate: cfg.baudRate,
      dataBits: cfg.dataBits,
      parity: cfg.parity,
      stopBits: cfg.stopBits,
      rtscts: cfg.flow === 'rtscts',
      xon: cfg.flow === 'xonxoff',
      xoff: cfg.flow === 'xonxoff',
      hupcl: false,      // ne pas couper DTR à la fermeture
      lock: true,        // Linux / macOS : refuse un port déjà ouvert ailleurs
      autoOpen: false,
    });
    p.open((err) => {
      if (err) return reject(new Error(`${cfg.path} ${classifyOpenError(err).message}`));
      // DTR / RTS inactifs : limite les redémarrages d'Arduino / ESP32
      p.set({ dtr: false, rts: false }, () => resolve(p));
    });
  });
}

/** Teste si un port peut être ouvert, puis le referme aussitôt. */
export async function checkPort(portPath: string): Promise<PortCheck> {
  try {
    const p = await openPort(withDefaults({ path: portPath, baudRate: 9600 }) as Required<SerialConfig>);
    await new Promise<void>((resolve) => p.close(() => resolve()));
    return { status: 'free', message: 'disponible' };
  } catch (err) {
    return classifyOpenError(err);
  }
}

/** Contenu des fichiers de protocole *.json de `dir` (texte brut, à passer à parseProtocol côté renderer). */
export async function readProtocolFiles(dir?: string): Promise<RawMessageFile[]> {
  if (!dir) return [];
  let names: string[];
  try {
    names = await fs.readdir(dir);
  } catch {
    return [];
  }
  const files = names.filter((n) => n.toLowerCase().endsWith('.json')).sort();
  return Promise.all(
    files.map(async (fileName) => ({ fileName, content: await fs.readFile(path.join(dir, fileName), 'utf-8') })),
  );
}

/** Contenu des Msg_*.json de `dir` (texte brut, validé ensuite côté renderer). */
export async function readMessageFiles(dir?: string): Promise<RawMessageFile[]> {
  if (!dir) return [];
  let names: string[];
  try {
    names = await fs.readdir(dir);
  } catch {
    return [];
  }
  const files = names.filter(isMessageFileName).sort();
  return Promise.all(
    files.map(async (fileName) => ({ fileName, content: await fs.readFile(path.join(dir, fileName), 'utf-8') })),
  );
}
