/**
 * Contrat entre la logique série (SerialLink) et le moyen d'accès au port.
 *
 * Implémentation fournie : pont IPC Electron (serialport côté process principal).
 * On peut en écrire d'autres (Web Serial, WebSocket vers un appareil réseau,
 * port simulé pour les tests) sans toucher au reste.
 */

export type DataBits = 5 | 6 | 7 | 8;
export type Parity = 'none' | 'even' | 'odd' | 'mark' | 'space';
export type StopBits = 1 | 1.5 | 2;
export type FlowControl = 'none' | 'rtscts' | 'xonxoff';

export interface SerialFormat {
  baudRate: number;
  dataBits?: DataBits;     // défaut 8
  parity?: Parity;         // défaut 'none'
  stopBits?: StopBits;     // défaut 1
  flow?: FlowControl;      // défaut 'none'
}

export interface SerialConfig extends SerialFormat {
  path: string;            // 'COM3', '/dev/ttyUSB0'
}

export interface PortInfo {
  path: string;
  description: string;     // ex. 'USB-SERIAL CH340' (vide si inconnu)
  manufacturer?: string;
  vendorId?: string;
  productId?: string;
  serialNumber?: string;
}

/** free = libre, busy = occupé par un autre programme, missing = absent, error = autre erreur */
export type PortStatus = 'free' | 'busy' | 'missing' | 'error';

export interface PortCheck {
  status: PortStatus;
  message: string;         // message lisible, en français
}

export interface Signals {
  dtr?: boolean;
  rts?: boolean;
}

export interface SerialTransport {
  listPorts(): Promise<PortInfo[]>;
  checkPort(path: string): Promise<PortCheck>;
  /** Ouvre le port, DTR et RTS inactifs. Rejette avec un message lisible. */
  open(config: SerialConfig): Promise<void>;
  /** Change les réglages du port ouvert (à chaud si possible). */
  reconfigure(format: Partial<SerialFormat>): Promise<void>;
  close(): Promise<void>;
  write(data: Uint8Array): Promise<void>;
  setSignals(signals: Signals): Promise<void>;
  /** Octets reçus, par morceaux. Retourne la fonction de désabonnement. */
  onData(listener: (chunk: Uint8Array) => void): () => void;
  /** Fermeture non demandée (câble retiré, erreur). */
  onClose(listener: (reason: string) => void): () => void;
}

export const DEFAULT_FORMAT: Required<SerialFormat> = {
  baudRate: 115200,
  dataBits: 8,
  parity: 'none',
  stopBits: 1,
  flow: 'none',
};

export const BAUD_RATES = [1200, 2400, 4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600];

export function withDefaults<T extends Partial<SerialFormat>>(cfg: T): T & Required<SerialFormat> {
  return { ...DEFAULT_FORMAT, ...cfg } as T & Required<SerialFormat>;
}

/** 'COM3 @ 115200 8N1' */
export function describeConfig(cfg: SerialConfig): string {
  const c = withDefaults(cfg);
  const text = `${c.path} @ ${c.baudRate} ${c.dataBits}${c.parity[0].toUpperCase()}${c.stopBits}`;
  return c.flow === 'none' ? text : `${text} ${c.flow}`;
}
