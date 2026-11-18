/**
 * Chaîne complète sans Electron : SerialLink -> pont preload -> handlers main -> serialport -> port virtuel (pty).
 * Linux uniquement (nécessite python3 pour créer la paire pty).
 */
import { spawn, type ChildProcess } from 'node:child_process';
import { EventEmitter } from 'node:events';
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest';

vi.mock('electron', () => ({ contextBridge: {}, ipcRenderer: {} }));

import { registerSerialHexIpc } from '../src/electron/main';
import { createSerialHexBridge } from '../src/electron/preload';
import { SerialLink, type LinkEvent } from '../src/link/serialLink';
import { toHex } from '../src/core/frames';
import { parseProtocol } from '../src/core/protocol';

const linux = process.platform === 'linux';
let device: ChildProcess;
let devPath = '';

// Faux IPC : relie ipcRenderer.invoke aux handlers de ipcMain, et webContents.send aux listeners du renderer
function fakeIpc() {
  const handlers = new Map<string, (e: unknown, ...a: unknown[]) => unknown>();
  const renderer = new EventEmitter();
  const sender = Object.assign(new EventEmitter(), {
    isDestroyed: () => false,
    send: (ch: string, payload: unknown) => renderer.emit(ch, {}, structuredClone(payload)),
  });
  const ipcMain = {
    handle: (ch: string, fn: (e: unknown, ...a: unknown[]) => unknown) => handlers.set(ch, fn),
    removeHandler: (ch: string) => handlers.delete(ch),
  };
  const ipcRenderer = {
    invoke: (ch: string, ...a: unknown[]) => handlers.get(ch)!({ sender }, ...a.map((x) => structuredClone(x))),
    on: (ch: string, l: (...a: any[]) => void) => renderer.on(ch, l),
    removeListener: (ch: string, l: (...a: any[]) => void) => renderer.removeListener(ch, l),
  };
  return { ipcMain, ipcRenderer };
}

// « Appareil » simulé : écho de chaque trame reçue, précédée de 0xEE
const DEVICE = `
import os, pty, sys, tty, select
m, s = pty.openpty(); tty.setraw(m); tty.setraw(s)
print(os.ttyname(s), flush=True)
while True:
    r, _, _ = select.select([m, sys.stdin], [], [])
    if sys.stdin in r: break
    data = os.read(m, 256)
    os.write(m, b'\\xEE' + data)
`;

describe.runIf(linux)('Electron main + preload + SerialLink sur port virtuel', () => {
  beforeAll(async () => {
    device = spawn('python3', ['-c', DEVICE]);
    devPath = await new Promise<string>((res) => device.stdout!.once('data', (d) => res(String(d).trim())));
  });
  afterAll(() => device.kill());

  it('connecte, échange des trames, change la vitesse, détecte un port occupé', async () => {
    const { ipcMain, ipcRenderer } = fakeIpc();
    const unregister = registerSerialHexIpc(ipcMain as never, {
      messagesDir: new URL('../../tests/data/messages', import.meta.url).pathname,
      protocolsDir: new URL('../../tests/data/protocols', import.meta.url).pathname,
    });
    const bridge = createSerialHexBridge(ipcRenderer as never);
    const link = new SerialLink(bridge);
    const events: LinkEvent[] = [];
    link.onEvent((e) => events.push(e));

    expect((await bridge.readMessageFiles()).map((f) => f.fileName)).toContain('Msg_Modbus.json');
    const protocols = await bridge.readProtocolFiles();
    expect(protocols.map((f) => f.fileName)).toContain('exemple_generique.json');
    const generic = protocols.find((f) => f.fileName === 'exemple_generique.json')!;
    expect(parseProtocol(generic.content, generic.fileName).name).toBe('Exemple générique');
    expect(await link.checkPort(devPath)).toEqual({ status: 'free', message: 'disponible' });
    expect((await link.checkPort('/dev/ttyNEXISTEPAS')).status).toBe('missing');

    await link.connect({ path: devPath, baudRate: 115200 });
    expect(link.getState().connected).toBe(true);
    expect((await link.checkPort(devPath)).status).toBe('busy');

    await link.sendMessage({ name: 'Ping', frame: ['AA 55 01 00', '{cs}'], checksum: { start: 2 } });
    await new Promise((r) => setTimeout(r, 150));
    const rx = events.filter((e) => e.kind === 'rx').map((e) => toHex((e as { data: Uint8Array }).data));
    expect(rx).toEqual(['EE AA 55 01 00 01']);

    await link.reconfigure({ baudRate: 9600 });
    expect(link.getState().config?.baudRate).toBe(9600);

    await link.disconnect();
    expect(link.getState().connected).toBe(false);
    expect((await link.checkPort(devPath)).status).toBe('free');
    unregister();
  });
});
