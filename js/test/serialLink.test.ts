import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { SerialLink, type LinkEvent } from '../src/link/serialLink';
import type { SerialTransport } from '../src/link/types';
import { toHex } from '../src/core/frames';

/** Transport simulé : enregistre les écritures, permet d'injecter des octets reçus. */
function fakeTransport() {
  const data = new Set<(c: Uint8Array) => void>();
  const close = new Set<(r: string) => void>();
  const written: string[] = [];
  const t: SerialTransport & { receive(hex: string): void; lose(r: string): void; written: string[] } = {
    written,
    listPorts: async () => [{ path: 'COM3', description: 'CH340' }],
    checkPort: async () => ({ status: 'free', message: 'disponible' }),
    open: vi.fn(async (cfg) => { if (cfg.path === 'COM9') throw new Error('COM9 déjà utilisé par un autre programme'); }),
    reconfigure: vi.fn(async () => {}),
    close: vi.fn(async () => {}),
    write: async (d) => { written.push(toHex(d)); },
    setSignals: vi.fn(async () => {}),
    onData: (l) => { data.add(l); return () => data.delete(l); },
    onClose: (l) => { close.add(l); return () => close.delete(l); },
    receive: (hex) => data.forEach((l) => l(Uint8Array.from(hex.split(' ').map((h) => parseInt(h, 16))))),
    lose: (r) => close.forEach((l) => l(r)),
  };
  return t;
}

describe('SerialLink', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it('connecte, envoie, reçoit en trames et compte les octets', async () => {
    const t = fakeTransport();
    const link = new SerialLink(t);
    const events: LinkEvent[] = [];
    link.onEvent((e) => events.push(e));

    await link.connect({ path: 'COM3', baudRate: 115200 });
    expect(link.getState()).toMatchObject({ connected: true, config: { path: 'COM3', dataBits: 8, parity: 'none' } });

    const msg = { name: 'Ping', frame: ['AA 55 01 00', '{cs}'], checksum: { algo: 'xor8' as const, start: 2 } };
    expect(await link.sendMessage(msg)).toBe(true);
    expect(t.written).toEqual(['AA 55 01 00 01']);

    t.receive('01 02'); vi.advanceTimersByTime(5);
    t.receive('03');    vi.advanceTimersByTime(25);   // silence > 20 ms : fin de trame
    t.receive('10');    vi.advanceTimersByTime(25);

    const rx = events.filter((e) => e.kind === 'rx').map((e) => toHex((e as { data: Uint8Array }).data));
    expect(rx).toEqual(['01 02 03', '10']);
    expect(link.getState()).toMatchObject({ txBytes: 5, rxBytes: 4 });
    expect(events[0]).toMatchObject({ kind: 'info', text: 'Connecté : COM3 @ 115200 8N1' });
  });

  it('change la vitesse à chaud', async () => {
    const t = fakeTransport();
    const link = new SerialLink(t);
    await link.connect({ path: 'COM3', baudRate: 115200 });
    await link.reconfigure({ baudRate: 9600 });
    expect(t.reconfigure).toHaveBeenCalledWith({ baudRate: 9600 });
    expect(link.getState().config?.baudRate).toBe(9600);
    await link.reconfigure({ baudRate: 9600 });          // inchangé : pas d'appel
    expect(t.reconfigure).toHaveBeenCalledTimes(1);
  });

  it('signale un port occupé et la perte de connexion', async () => {
    const t = fakeTransport();
    const link = new SerialLink(t);
    const errors: string[] = [];
    link.onEvent((e) => e.kind === 'error' && errors.push(e.text));

    await expect(link.connect({ path: 'COM9', baudRate: 9600 })).rejects.toThrow('déjà utilisé');
    expect(link.getState().connected).toBe(false);

    await link.connect({ path: 'COM3', baudRate: 9600 });
    t.lose('câble débranché');
    expect(link.getState().connected).toBe(false);
    expect(await link.send(Uint8Array.of(1))).toBe(false);
    expect(errors).toEqual([
      'Connexion impossible : COM9 déjà utilisé par un autre programme',
      'Perte de connexion : câble débranché',
      'Envoi impossible : port non connecté',
    ]);
  });

  it("refuse d'envoyer un message invalide", async () => {
    const t = fakeTransport();
    const link = new SerialLink(t);
    await link.connect({ path: 'COM3', baudRate: 9600 });
    const msg = { name: 'LED', frame: ['{led}'], params: { led: { type: 'u8' as const, max: 8 } } };
    expect(await link.sendMessage(msg, { led: 9 })).toBe(false);
    expect(t.written).toEqual([]);
  });
});
