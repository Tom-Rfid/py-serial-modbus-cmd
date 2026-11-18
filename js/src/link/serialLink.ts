/**
 * link/serialLink.ts — La liaison série vue par l'application.
 *
 * Équivalent de SerialLink en Python. Regroupe :
 *   - l'état de la liaison (connecté, réglages, compteurs TX / RX, DTR / RTS)
 *   - la connexion, la reconfiguration à chaud, la déconnexion
 *   - l'envoi d'octets ou de messages (construction de la trame comprise)
 *   - la réception, découpée en trames par FrameAssembler
 *   - un journal d'événements (tx, rx, info, error) avec des messages en français
 *
 * L'accès réel au port est délégué à un SerialTransport (pont IPC Electron,
 * ou autre) : cette classe ne dépend ni d'Electron, ni de Node, ni de React.
 *
 * Deux façons de suivre ce qui se passe :
 *   - subscribe / getState : l'état a changé (compatible useSyncExternalStore de React)
 *   - onEvent              : un événement à afficher dans un journal
 *
 *   const link = new SerialLink(transport);
 *   link.subscribe(() => render(link.getState()));
 *   link.onEvent((e) => appendToLog(e));
 *   await link.connect({ path: 'COM3', baudRate: 115200 });
 *   await link.sendMessage(msg, { led: 2 });
 */
import { FrameAssembler } from '../core/framer';
import { buildFrame } from '../core/frames';
import type { MessageDef, ParamValues } from '../core/types';
import {
  describeConfig, withDefaults,
  type PortCheck, type PortInfo, type SerialConfig, type SerialFormat, type SerialTransport, type Signals,
} from './types';

/** État de la liaison. Remplacé par un nouvel objet à chaque changement (jamais modifié en place). */
export interface LinkState {
  connected: boolean;
  /** Opération en cours (ouverture, fermeture, reconfiguration). */
  pending: boolean;
  config: Required<SerialConfig> | null;
  signals: Required<Signals>;
  txBytes: number;
  rxBytes: number;
}

/** Événement du journal. `time` = horodatage en ms (Date.now()). */
export type LinkEvent =
  | { kind: 'tx'; time: number; data: Uint8Array; label?: string }
  | { kind: 'rx'; time: number; data: Uint8Array }
  | { kind: 'info'; time: number; text: string }
  | { kind: 'error'; time: number; text: string };

const INITIAL: LinkState = {
  connected: false,
  pending: false,
  config: null,
  signals: { dtr: false, rts: false },
  txBytes: 0,
  rxBytes: 0,
};

export class SerialLink {
  private state: LinkState = INITIAL;
  // Abonnés : changements d'état, et événements du journal
  private stateListeners = new Set<() => void>();
  private eventListeners = new Set<(e: LinkEvent) => void>();
  private framer: FrameAssembler;
  private unsubscribers: (() => void)[] = [];   // désabonnements du transport (dispose)
  // Compteur RX tenu à jour à chaque morceau reçu, mais publié dans l'état
  // seulement à chaque trame complète : évite un rafraîchissement d'écran par morceau.
  private rxCount = 0;

  /**
   * transport : accès au port (ex. window.serialhex fourni par le preload)
   * gapMs     : silence (ms) qui termine une trame reçue, 20 par défaut
   */
  constructor(private readonly transport: SerialTransport, options: { gapMs?: number } = {}) {
    // Chaque trame complète est publiée dans le journal et met à jour le compteur RX
    this.framer = new FrameAssembler((frame) => {
      this.emit({ kind: 'rx', time: Date.now(), data: frame });
      this.setState({ rxBytes: this.rxCount });
    }, options.gapMs ?? 20);
    // Branchement sur le transport : octets reçus, et fermeture non demandée
    this.unsubscribers.push(
      transport.onData((chunk) => {
        this.rxCount += chunk.length;
        this.framer.push(chunk);
      }),
      transport.onClose((reason) => this.handleLost(reason)),
    );
  }

  // ------------------------------------------------------------------
  // État (compatible useSyncExternalStore)
  // ------------------------------------------------------------------
  // Fonctions fléchées : elles peuvent être passées telles quelles
  // (ex. useSyncExternalStore(link.subscribe, link.getState)) sans perdre `this`.
  getState = (): LinkState => this.state;

  subscribe = (listener: () => void): (() => void) => {
    this.stateListeners.add(listener);
    return () => this.stateListeners.delete(listener);
  };

  /** Abonnement au journal. Retourne la fonction de désabonnement. */
  onEvent(listener: (e: LinkEvent) => void): () => void {
    this.eventListeners.add(listener);
    return () => this.eventListeners.delete(listener);
  }

  /** Crée un nouvel état (copie + modifications) et prévient les abonnés. */
  private setState(patch: Partial<LinkState>) {
    this.state = { ...this.state, ...patch };
    this.stateListeners.forEach((l) => l());
  }

  private emit(e: LinkEvent) {
    this.eventListeners.forEach((l) => l(e));
  }

  /** Ajoute une ligne d'information au journal (utilisable par l'application). */
  info(text: string) {
    this.emit({ kind: 'info', time: Date.now(), text });
  }

  /** Ajoute une ligne d'erreur au journal (utilisable par l'application). */
  error(text: string) {
    this.emit({ kind: 'error', time: Date.now(), text });
  }

  /** Silence (ms) qui termine une trame reçue. Modifiable à tout moment. */
  get gapMs() {
    return this.framer.gapMs;
  }

  set gapMs(ms: number) {
    if (ms >= 1) this.framer.gapMs = ms;
  }

  // ------------------------------------------------------------------
  // Ports
  // ------------------------------------------------------------------
  listPorts(): Promise<PortInfo[]> {
    return this.transport.listPorts();
  }

  /** Port libre / occupé / absent. Le port connecté par nous est signalé sans le rouvrir. */
  async checkPort(path: string): Promise<PortCheck> {
    if (this.state.connected && this.state.config?.path === path) {
      return { status: 'busy', message: 'connecté (utilisé par cette application)' };
    }
    return this.transport.checkPort(path);
  }

  // ------------------------------------------------------------------
  // Connexion
  // ------------------------------------------------------------------
  /**
   * Ouvre le port. Les réglages absents prennent les valeurs par défaut (8N1).
   * En cas d'échec : erreur journalisée ET levée (ex. « COM3 déjà utilisé... »).
   */
  async connect(config: SerialConfig): Promise<void> {
    if (this.state.connected) await this.disconnect();
    const full = withDefaults(config) as Required<SerialConfig>;
    this.setState({ pending: true });
    try {
      await this.transport.open(full);
    } catch (e) {
      this.setState({ pending: false });
      this.error(`Connexion impossible : ${message(e)}`);
      throw e;
    }
    // Nouvelle connexion : on repart de zéro (trame en cours, compteurs, DTR / RTS)
    this.framer.reset();
    this.rxCount = 0;
    this.setState({
      connected: true, pending: false, config: full,
      signals: { dtr: false, rts: false }, txBytes: 0, rxBytes: 0,
    });
    this.info(`Connecté : ${describeConfig(full)}`);
  }

  /** Ferme le port. Sans effet si déjà déconnecté. */
  async disconnect(): Promise<void> {
    if (!this.state.connected) return;
    this.setState({ pending: true });
    try {
      await this.transport.close();
    } finally {
      this.framer.flush();      // publie ce qui avait été reçu avant la fermeture
      this.setState({ connected: false, pending: false });
      this.info('Déconnecté');
    }
  }

  /** Change vitesse / format sans se déconnecter. */
  async reconfigure(format: Partial<SerialFormat>): Promise<void> {
    const current = this.state.config;
    if (!this.state.connected || !current) return;
    // Rien à faire si aucune valeur ne change (évite une coupure inutile du port)
    const changed = Object.entries(format).some(([k, v]) => v !== undefined && current[k as keyof SerialFormat] !== v);
    if (!changed) return;
    this.setState({ pending: true });
    try {
      await this.transport.reconfigure(format);
    } catch (e) {
      this.setState({ pending: false });
      this.error(`Réglage refusé : ${message(e)}`);
      throw e;
    }
    const config = { ...current, ...stripUndefined(format) } as Required<SerialConfig>;
    this.setState({ pending: false, config });
    this.info(`Réglages appliqués : ${describeConfig(config)}`);
  }

  /** Active / désactive DTR et RTS ({ dtr: true }, { rts: false }...). */
  async setSignals(signals: Signals): Promise<void> {
    if (!this.state.connected) return;
    await this.transport.setSignals(signals);
    this.setState({ signals: { ...this.state.signals, ...stripUndefined(signals) } });
  }

  /** Le transport signale une fermeture non demandée (câble retiré, erreur). */
  private handleLost(reason: string) {
    if (!this.state.connected) return;
    this.framer.flush();
    this.setState({ connected: false, pending: false });
    this.error(`Perte de connexion : ${reason}`);
  }

  // ------------------------------------------------------------------
  // Envoi
  // ------------------------------------------------------------------
  /** Envoie des octets. Retourne false (et journalise l'erreur) en cas d'échec. */
  async send(data: Uint8Array, label?: string): Promise<boolean> {
    if (!this.state.connected) {
      this.error('Envoi impossible : port non connecté');
      return false;
    }
    try {
      await this.transport.write(data);
    } catch (e) {
      this.error(`Envoi impossible : ${message(e)}`);
      return false;
    }
    this.setState({ txBytes: this.state.txBytes + data.length });
    this.emit({ kind: 'tx', time: Date.now(), data, label });
    return true;
  }

  /** Construit la trame d'un message et l'envoie. */
  async sendMessage(msg: MessageDef, values: ParamValues = {}): Promise<boolean> {
    let frame: Uint8Array;
    try {
      frame = buildFrame(msg, values);
    } catch (e) {
      this.error(`${msg.name} : ${message(e)}`);
      return false;
    }
    return this.send(frame, msg.name);
  }

  /** Envoie plusieurs messages à la suite. S'arrête à la première erreur ou si signal est annulé. */
  async sendSequence(
    items: { msg: MessageDef; values?: ParamValues }[],
    delayMs: number,
    signal?: AbortSignal,
  ): Promise<boolean> {
    for (let i = 0; i < items.length; i++) {
      if (signal?.aborted) return false;
      if (!(await this.sendMessage(items[i].msg, items[i].values))) return false;
      if (i < items.length - 1 && delayMs > 0) await sleep(delayMs, signal);
    }
    return true;
  }

  /** Libère la liaison (désabonnements). À appeler si l'instance n'est plus utilisée. */
  dispose() {
    this.unsubscribers.forEach((u) => u());
    this.framer.reset();
    this.stateListeners.clear();
    this.eventListeners.clear();
  }
}

/** Texte d'une erreur, quel que soit son type. */
function message(e: unknown): string {
  return e instanceof Error ? e.message : String(e);
}

/** Retire les clés à undefined (pour ne pas écraser une valeur existante). */
function stripUndefined<T extends object>(o: T): Partial<T> {
  return Object.fromEntries(Object.entries(o).filter(([, v]) => v !== undefined)) as Partial<T>;
}

/** Attend `ms` millisecondes, ou moins si `signal` est annulé. */
function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const t = setTimeout(resolve, ms);
    signal?.addEventListener('abort', () => {
      clearTimeout(t);
      resolve();
    }, { once: true });
  });
}
