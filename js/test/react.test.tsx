// @vitest-environment jsdom
import { act, renderHook, waitFor } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { SerialLink } from '../src/link/serialLink';
import type { SerialTransport } from '../src/link/types';
import { useLinkLog, useLinkState, useMessageForm, useMessages, usePortCheck, useSerialPorts } from '../src/react';

const transport: SerialTransport = {
  listPorts: async () => [{ path: 'COM3', description: 'CH340' }],
  checkPort: async () => ({ status: 'free', message: 'disponible' }),
  open: async () => {}, reconfigure: async () => {}, close: async () => {},
  write: async () => {}, setSignals: async () => {},
  onData: () => () => {}, onClose: () => () => {},
};

const LED = {
  name: 'LED', group: 'Sorties', frame: ['AA', '{led}', '{cs}'],
  params: { led: { type: 'u8' as const, default: 1, max: 8 } },
};

describe('hooks React', () => {
  it('useLinkState et useLinkLog suivent la liaison', async () => {
    const link = new SerialLink(transport);
    const { result } = renderHook(() => ({ state: useLinkState(link), log: useLinkLog(link, 100, 1) }));
    expect(result.current.state.connected).toBe(false);
    await act(() => link.connect({ path: 'COM3', baudRate: 9600 }));
    expect(result.current.state.connected).toBe(true);
    await act(() => link.send(Uint8Array.of(1, 2), 'test'));
    await waitFor(() => expect(result.current.log.entries.map((e) => e.event.kind)).toEqual(['info', 'tx']));
    expect(result.current.state.txBytes).toBe(2);
  });

  it('useSerialPorts et usePortCheck', async () => {
    const link = new SerialLink(transport);
    const { result } = renderHook(() => {
      const { ports } = useSerialPorts(link, 0);
      return { ports, ...usePortCheck(link, 'COM3', ports) };
    });
    await waitFor(() => expect(result.current.check).toEqual({ status: 'free', message: 'disponible' }));
    expect(result.current.ports[0].path).toBe('COM3');
  });

  it('useMessageForm calcule la trame et garde les valeurs par message', () => {
    const OTHER = { name: 'Autre', frame: ['01'] };
    const { result, rerender } = renderHook(({ msg }) => useMessageForm(msg), { initialProps: { msg: LED as never } });
    expect(result.current.hex).toBe('AA 01 AB');
    act(() => result.current.setValue('led', 9));
    expect(result.current.error).toContain('max');
    act(() => result.current.setValue('led', '0x02'));
    expect(result.current.hex).toBe('AA 02 A8');
    rerender({ msg: OTHER as never });
    expect(result.current.hex).toBe('01');
    rerender({ msg: LED as never });
    expect(result.current.hex).toBe('AA 02 A8');   // valeur conservée
  });

  it('useMessages charge et groupe', async () => {
    const loader = async () => [{ fileName: 'Msg_Sorties.json', content: { messages: [LED] } }];
    const { result } = renderHook(() => useMessages(loader));
    await waitFor(() => expect(result.current.groups.map((g) => g.group)).toEqual(['Sorties']));
  });
});
