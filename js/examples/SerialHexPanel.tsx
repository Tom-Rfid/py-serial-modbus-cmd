/**
 * Exemple d'intégration React : l'équivalent de l'interface Python, en ~200 lignes.
 * À copier dans ton application et à habiller avec tes propres composants.
 *
 *   import { SerialHexPanel } from './SerialHexPanel';
 *   <SerialHexPanel />
 */
import { useEffect, useMemo, useState } from 'react';

import {
  BAUD_RATES, SerialLink, getSerialHexBridge, toAscii, toHex,
  type MessageDef, type ParamDef, type Parity, type DataBits, type StopBits, type FlowControl,
} from 'serialhex';
import {
  messageKey, useLinkLog, useLinkState, useMessageForm, useMessages, usePeriodic, usePortCheck, useSerialPorts,
} from 'serialhex/react';

// Une seule liaison pour toute l'application (à placer dans un contexte si plusieurs écrans l'utilisent)
const bridge = getSerialHexBridge();
const link = new SerialLink(bridge);
const loadMessages = () => bridge.readMessageFiles();

const STATUS_COLOR = { free: '#1a8a3a', busy: '#c0392b', missing: '#999', error: '#d68910' };

export function SerialHexPanel() {
  const [selected, setSelected] = useState<MessageDef | null>(null);
  return (
    <div style={{ display: 'grid', gridTemplateRows: 'auto 1fr 240px', gap: 8, height: '100%' }}>
      <ComBar />
      <div style={{ display: 'grid', gridTemplateColumns: '280px 1fr', gap: 8, minHeight: 0 }}>
        <MessageList selected={selected} onSelect={setSelected} />
        <ParamForm msg={selected} />
      </div>
      <Monitor />
    </div>
  );
}

// ----------------------------------------------------------------------
// Liaison série
// ----------------------------------------------------------------------
function ComBar() {
  const state = useLinkState(link);
  const { ports, refresh } = useSerialPorts(link);
  const [path, setPath] = useState<string | null>(null);
  const [baudRate, setBaudRate] = useState(115200);
  const [dataBits, setDataBits] = useState<DataBits>(8);
  const [parity, setParity] = useState<Parity>('none');
  const [stopBits, setStopBits] = useState<StopBits>(1);
  const [flow, setFlow] = useState<FlowControl>('none');
  const { check, recheck } = usePortCheck(link, path, ports);

  // Sélectionne le premier port disponible
  useEffect(() => {
    if (!path && ports.length) setPath(ports[0].path);
  }, [ports, path]);

  // Réglages modifiés pendant la connexion : appliqués à chaud
  useEffect(() => {
    if (state.connected) link.reconfigure({ baudRate, dataBits, parity, stopBits, flow }).catch(() => {});
  }, [baudRate, dataBits, parity, stopBits, flow]); // eslint-disable-line react-hooks/exhaustive-deps

  const toggle = () =>
    state.connected
      ? link.disconnect()
      : path && link.connect({ path, baudRate, dataBits, parity, stopBits, flow }).catch(() => {});

  return (
    <fieldset>
      <legend>Liaison série</legend>
      <select value={path ?? ''} disabled={state.connected} onChange={(e) => setPath(e.target.value)}>
        {ports.map((p) => (
          <option key={p.path} value={p.path}>{p.description ? `${p.path} — ${p.description}` : p.path}</option>
        ))}
      </select>
      <button onClick={() => { void refresh(); recheck(); }}>Actualiser</button>
      {check && <span style={{ color: STATUS_COLOR[check.status] }}> ● {check.message}</span>}
      <br />
      <input list="bauds" value={baudRate} onChange={(e) => setBaudRate(Number(e.target.value) || baudRate)} />
      <datalist id="bauds">{BAUD_RATES.map((b) => <option key={b} value={b} />)}</datalist>
      <select value={dataBits} onChange={(e) => setDataBits(Number(e.target.value) as DataBits)}>
        {[5, 6, 7, 8].map((d) => <option key={d}>{d}</option>)}
      </select>
      <select value={parity} onChange={(e) => setParity(e.target.value as Parity)}>
        {['none', 'even', 'odd', 'mark', 'space'].map((p) => <option key={p}>{p}</option>)}
      </select>
      <select value={stopBits} onChange={(e) => setStopBits(Number(e.target.value) as StopBits)}>
        {[1, 1.5, 2].map((s) => <option key={s}>{s}</option>)}
      </select>
      <select value={flow} onChange={(e) => setFlow(e.target.value as FlowControl)}>
        {['none', 'rtscts', 'xonxoff'].map((f) => <option key={f}>{f}</option>)}
      </select>
      <br />
      <button onClick={toggle} disabled={state.pending || (!state.connected && !path)}>
        {state.connected ? 'Déconnecter' : 'Connecter'}
      </button>
      <span style={{ color: state.connected ? '#1a8a3a' : '#999' }}> ● </span>
      {state.connected ? `Connecté — ${state.config!.path} @ ${state.config!.baudRate}` : 'Déconnecté'}
      {state.connected && (
        <>
          <label><input type="checkbox" checked={state.signals.dtr} onChange={(e) => link.setSignals({ dtr: e.target.checked })} />DTR</label>
          <label><input type="checkbox" checked={state.signals.rts} onChange={(e) => link.setSignals({ rts: e.target.checked })} />RTS</label>
          <span> TX {state.txBytes} o · RX {state.rxBytes} o</span>
        </>
      )}
    </fieldset>
  );
}

// ----------------------------------------------------------------------
// Messages
// ----------------------------------------------------------------------
function MessageList({ selected, onSelect }: { selected: MessageDef | null; onSelect: (m: MessageDef) => void }) {
  const { groups, errors, reload } = useMessages(loadMessages);
  return (
    <div style={{ overflow: 'auto' }}>
      <button onClick={reload}>Recharger</button>
      {errors.map((e) => <div key={e.fileName} style={{ color: '#c0392b' }}>{e.fileName} : {e.error}</div>)}
      {groups.map((g) => (
        <div key={g.group}>
          <strong>{g.group}</strong>
          {g.messages.map((m) => (
            <div
              key={messageKey(m)}
              onClick={() => onSelect(m)}
              onDoubleClick={() => link.sendMessage(m)}
              style={{ paddingLeft: 12, cursor: 'pointer', background: selected === m ? '#dde7f5' : undefined }}
            >
              {m.name}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}

function ParamForm({ msg }: { msg: MessageDef | null }) {
  const { values, setValue, frame, hex, error } = useMessageForm(msg);
  const [repeat, setRepeat] = useState(false);
  const [periodMs, setPeriodMs] = useState(1000);
  const { connected } = useLinkState(link);

  useEffect(() => setRepeat(false), [msg, connected]);
  usePeriodic(() => (frame && msg ? link.send(frame, msg.name) : false), periodMs, repeat, () => setRepeat(false));

  if (!msg) return <div>Sélectionne un message</div>;
  return (
    <div>
      <h3>{msg.name}</h3>
      {msg.description && <p style={{ color: 'gray' }}>{msg.description}</p>}
      <table>
        <tbody>
          {Object.entries(msg.params ?? {}).map(([name, pdef]) => (
            <tr key={name}>
              <td>{pdef.label ?? name}</td>
              <td><ParamInput pdef={pdef} value={values[name]} onChange={(v) => setValue(name, v)} /></td>
              <td style={{ color: 'gray' }}>{pdef.type ?? 'u8'} {pdef.unit}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <pre style={{ color: error ? '#c0392b' : undefined }}>{error ?? `${hex}   (${frame!.length} octets)`}</pre>
      <button disabled={!frame} onClick={() => frame && link.send(frame, msg.name)}>Envoyer</button>
      <label>
        <input type="checkbox" checked={repeat} disabled={!frame} onChange={(e) => setRepeat(e.target.checked)} />
        Répéter toutes les
      </label>
      <input type="number" value={periodMs} min={10} onChange={(e) => setPeriodMs(Number(e.target.value))} /> ms
    </div>
  );
}

function ParamInput({ pdef, value, onChange }: { pdef: ParamDef; value: unknown; onChange: (v: string | boolean) => void }) {
  if (pdef.type === 'bool')
    return <input type="checkbox" checked={['1', 'true', 'on', 'oui', 'yes'].includes(String(value).toLowerCase())}
                  onChange={(e) => onChange(e.target.checked)} />;
  if (pdef.type === 'enum')
    return (
      <select value={String(value)} onChange={(e) => onChange(e.target.value)}>
        {Object.keys(pdef.choices ?? {}).map((k) => <option key={k}>{k}</option>)}
      </select>
    );
  return <input value={String(value ?? '')} onChange={(e) => onChange(e.target.value)} style={{ fontFamily: 'monospace' }} />;
}

// ----------------------------------------------------------------------
// Moniteur
// ----------------------------------------------------------------------
const TAG_COLOR = { tx: '#1f5fbf', rx: '#1a8a3a', info: '#888', error: '#c0392b' };

function Monitor() {
  const { entries, clear } = useLinkLog(link);
  const lines = useMemo(() => entries.slice(-500), [entries]);
  return (
    <div style={{ display: 'flex', flexDirection: 'column', minHeight: 0 }}>
      <div>
        <strong>Moniteur</strong> <button onClick={clear}>Effacer</button>
      </div>
      <div style={{ overflow: 'auto', fontFamily: 'monospace', fontSize: 12, flex: 1 }}>
        {lines.map(({ id, event: e }) => (
          <div key={id} style={{ color: TAG_COLOR[e.kind] }}>
            {new Date(e.time).toLocaleTimeString()}{'  '}
            {e.kind === 'tx' || e.kind === 'rx'
              ? `${e.kind.toUpperCase()} [${e.data.length}]  ${toHex(e.data)}   |${toAscii(e.data)}|${e.kind === 'tx' && e.label ? `   ← ${e.label}` : ''}`
              : e.text}
          </div>
        ))}
      </div>
    </div>
  );
}
