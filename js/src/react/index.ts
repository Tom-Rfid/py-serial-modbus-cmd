/**
 * react/index.ts — Hooks React.
 *
 * Branchent un SerialLink sur des composants React. Ils ne fournissent aucun
 * rendu : l'apparence reste entièrement celle de l'application.
 *
 *   useLinkState     état de la liaison (connecté, réglages, compteurs)
 *   useSerialPorts   ports présents, rafraîchis périodiquement
 *   usePortCheck     port libre / occupé / absent
 *   useLinkLog       journal TX / RX / infos / erreurs
 *   useMessages      chargement des Msg_*.json
 *   useMessageForm   valeurs des paramètres d'un message + trame calculée
 *   usePeriodic      exécution périodique (envoi répété)
 *
 * Exemple complet : js/examples/SerialHexPanel.tsx
 */
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';

import { buildFrame, defaultsFor, toHex } from '../core/frames';
import { groupMessages, loadMessageFiles, type LoadResult, type RawMessageFile } from '../core/messages';
import type { MessageDef, ParamValue, ParamValues } from '../core/types';
import type { LinkEvent, LinkState, SerialLink } from '../link/serialLink';
import type { PortCheck, PortInfo } from '../link/types';

// ----------------------------------------------------------------------
// État de la liaison
// ----------------------------------------------------------------------

/** État courant de la liaison (connecté, config, compteurs...). */
export function useLinkState(link: SerialLink): LinkState {
  return useSyncExternalStore(link.subscribe, link.getState, link.getState);
}

// ----------------------------------------------------------------------
// Ports
// ----------------------------------------------------------------------

export interface UseSerialPorts {
  ports: PortInfo[];
  refresh: () => Promise<void>;
  error: string | null;
}

/** Liste des ports présents, rafraîchie toutes les `pollMs` (branchement / débranchement). */
export function useSerialPorts(link: SerialLink, pollMs = 1500): UseSerialPorts {
  const [ports, setPorts] = useState<PortInfo[]>([]);
  const [error, setError] = useState<string | null>(null);
  // Signature de la dernière liste : on ne met à jour l'état (et ne redessine)
  // que si la liste a réellement changé.
  const keyRef = useRef('');

  const refresh = useCallback(async () => {
    try {
      const list = await link.listPorts();
      const key = list.map((p) => `${p.path}|${p.description}`).join(';');
      if (key !== keyRef.current) {
        keyRef.current = key;
        setPorts(list);
      }
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }, [link]);

  useEffect(() => {
    void refresh();
    if (pollMs <= 0) return;
    const id = setInterval(() => void refresh(), pollMs);
    return () => clearInterval(id);
  }, [refresh, pollMs]);

  return { ports, refresh, error };
}

/**
 * État du port sélectionné : libre, occupé, absent.
 * Re-testé quand le port, la liste des ports ou l'état de connexion change.
 */
export function usePortCheck(link: SerialLink, path: string | null, ports: PortInfo[]) {
  const [check, setCheck] = useState<PortCheck | null>(null);
  const { connected } = useLinkState(link);
  const present = !!path && ports.some((p) => p.path === path);
  // Compteur incrémenté par recheck() pour forcer un nouveau test
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    let cancelled = false;
    if (!path) {
      setCheck(null);
      return;
    }
    if (!present) {
      setCheck({ status: 'missing', message: 'introuvable (débranché ?)' });
      return;
    }
    // `cancelled` ignore une réponse arrivée après un changement de port
    link.checkPort(path).then((c) => !cancelled && setCheck(c), (e) =>
      !cancelled && setCheck({ status: 'error', message: String(e) }));
    return () => {
      cancelled = true;
    };
  }, [link, path, present, connected, nonce]);

  const recheck = useCallback(() => setNonce((n) => n + 1), []);
  return { check, recheck };
}

// ----------------------------------------------------------------------
// Journal
// ----------------------------------------------------------------------

export interface LogEntry {
  id: number;
  event: LinkEvent;
}

/**
 * Journal des événements (TX, RX, info, erreurs), limité à `max` entrées.
 * Les mises à jour sont regroupées toutes les `batchMs` pour tenir les débits élevés.
 */
export function useLinkLog(link: SerialLink, max = 2000, batchMs = 50) {
  const [entries, setEntries] = useState<LogEntry[]>([]);
  // Événements reçus mais pas encore affichés : ils sont regroupés et ajoutés
  // en une fois toutes les `batchMs`, au lieu d'un rendu par trame reçue.
  const pending = useRef<LogEntry[]>([]);
  const nextId = useRef(0);

  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    const unsubscribe = link.onEvent((event) => {
      pending.current.push({ id: nextId.current++, event });
      if (!timer) {
        timer = setTimeout(() => {
          timer = null;
          const batch = pending.current;
          pending.current = [];
          setEntries((prev) => {
            const all = prev.concat(batch);
            return all.length > max ? all.slice(all.length - max) : all;
          });
        }, batchMs);
      }
    });
    return () => {
      unsubscribe();
      if (timer) clearTimeout(timer);
    };
  }, [link, max, batchMs]);

  const clear = useCallback(() => {
    pending.current = [];
    setEntries([]);
  }, []);

  return { entries, clear };
}

// ----------------------------------------------------------------------
// Messages
// ----------------------------------------------------------------------

/**
 * Charge les Msg_*.json via `loader` (par défaut : window.serialhex.readMessageFiles).
 */
export function useMessages(loader: () => Promise<RawMessageFile[]>) {
  const [result, setResult] = useState<LoadResult>({ messages: [], errors: [] });
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    try {
      setResult(loadMessageFiles(await loader()));
    } catch (e) {
      setResult({ messages: [], errors: [{ fileName: '', error: e instanceof Error ? e.message : String(e) }] });
    } finally {
      setLoading(false);
    }
  }, [loader]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const groups = useMemo(() => groupMessages(result.messages), [result.messages]);
  return { messages: result.messages, groups, errors: result.errors, loading, reload };
}

/** Clé stable d'un message : 'Groupe/Nom'. */
export function messageKey(msg: MessageDef): string {
  return `${msg.group ?? ''}/${msg.name}`;
}

/**
 * Formulaire de paramètres d'un message, avec aperçu de la trame.
 * Les valeurs saisies sont conservées par message quand on change de sélection.
 */
export function useMessageForm(msg: MessageDef | null) {
  // Valeurs saisies pour chaque message déjà affiché, par clé 'Groupe/Nom'
  const store = useRef(new Map<string, ParamValues>());
  const key = msg ? messageKey(msg) : '';
  const [values, setValues] = useState<ParamValues>(() => (msg ? defaultsFor(msg) : {}));

  // Changement de message : on reprend ses valeurs saisies, ou ses valeurs par défaut
  useEffect(() => {
    if (!msg) return setValues({});
    setValues(store.current.get(key) ?? defaultsFor(msg));
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps

  const setValue = useCallback((name: string, value: ParamValue) => {
    setValues((prev) => {
      const next = { ...prev, [name]: value };
      store.current.set(key, next);
      return next;
    });
  }, [key]);

  const reset = useCallback(() => {
    if (!msg) return;
    store.current.delete(key);
    setValues(defaultsFor(msg));
  }, [key, msg]);

  // Trame recalculée à chaque modification ; une valeur invalide donne `error`
  const preview = useMemo(() => {
    if (!msg) return { frame: null, hex: '', error: null };
    try {
      const frame = buildFrame(msg, values);
      return { frame, hex: toHex(frame), error: null };
    } catch (e) {
      return { frame: null, hex: '', error: e instanceof Error ? e.message : String(e) };
    }
  }, [msg, values]);

  return { values, setValue, reset, ...preview };
}

/** Appelle `fn` toutes les `ms` tant que `active` est vrai ; s'arrête si `fn` retourne false. */
export function usePeriodic(fn: () => Promise<boolean> | boolean, ms: number, active: boolean, onStop?: () => void) {
  // `fn` et `onStop` sont lus via des refs : le minuteur n'est pas relancé
  // à chaque rendu, seulement quand `active` ou `ms` change.
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const stopRef = useRef(onStop);
  stopRef.current = onStop;

  useEffect(() => {
    if (!active) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const tick = async () => {
      if (cancelled) return;
      const ok = await fnRef.current();
      if (cancelled) return;
      if (ok === false) return stopRef.current?.();
      timer = setTimeout(tick, Math.max(10, ms));
    };
    void tick();
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [active, ms]);
}
