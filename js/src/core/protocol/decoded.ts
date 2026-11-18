/**
 * core/protocol/decoded.ts — Résultat du décodage d'une trame (portage de core/protocol/decoded.py).
 */
import type { FrameKind } from './common';
import type { FieldColor, FieldRole } from './fields';

export interface DecodedField {
  name: string;
  start: number;
  raw: Uint8Array;
  /** Valeur numérique (undefined pour DATA, les CRC et les octets non lus). */
  value?: number;
  /** true / false pour les octets fixes et les CRC, undefined sinon. */
  ok?: boolean;
  note: string;
  role: FieldRole;
  color?: FieldColor;
  /** Position du premier bit dans la trame, et taille en bits. */
  bitStart?: number;
  bits?: number;
  /** Texte de la valeur ("values" du fichier de protocole). */
  meaning?: string;
  /** Description du champ (fichier de protocole). */
  description?: string;
}

/** Position lisible d'un champ : '0', '2-5' (octets), ou '1.4-2.1' (octet.bit) pour un champ en bits. */
export function fieldSpan(f: DecodedField): string {
  if (f.bits !== undefined && f.bitStart !== undefined && (f.bitStart % 8 || f.bits % 8)) {
    const first = f.bitStart;
    const last = f.bitStart + f.bits - 1;
    const at = (k: number) => `${Math.floor(k / 8)}.${k % 8}`;
    return first === last ? at(first) : `${at(first)}-${at(last)}`;
  }
  const end = f.start + f.raw.length - 1;
  return end <= f.start ? String(f.start) : `${f.start}-${end}`;
}

export class Decoded {
  fields: DecodedField[] = [];
  errors: string[] = [];
  complete = false;
  extra: Uint8Array = new Uint8Array();
  /** Nom de la variante de trame reconnue. */
  variant = '';
  /** Trame brute reçue et trame binaire décodée, si un codage (ASCII hexa) est utilisé. */
  encoded: Uint8Array = new Uint8Array();
  binary: Uint8Array = new Uint8Array();

  constructor(readonly kind: FrameKind) {}

  /** Complète, sans erreur ni octet en trop. */
  get ok(): boolean {
    return this.complete && this.errors.length === 0 && this.extra.length === 0;
  }

  get(name: string): number | undefined {
    return this.fields.find((f) => f.name === name)?.value;
  }

  byRole(role: FieldRole): DecodedField | undefined {
    return this.fields.find((f) => f.role === role);
  }

  // Champs repérés par leur rôle, quel que soit leur nom dans le fichier de conf
  get requestId() {
    return this.byRole('request_id')?.value;
  }
  get commandId() {
    return this.byRole('command_id')?.value;
  }
  get error() {
    return this.byRole('error')?.value;
  }
  get length() {
    return this.byRole('length')?.value;
  }
  /** Champ DATA, ou undefined s'il est absent ou vide. */
  get data(): DecodedField | undefined {
    const f = this.byRole('data');
    return f && f.raw.length ? f : undefined;
  }
  /** false si un CRC est faux, true s'il y en a et qu'ils sont justes, undefined sinon. */
  get crcOk(): boolean | undefined {
    const checks = this.fields.filter((f) => f.role === 'crc').map((f) => f.ok);
    return checks.length ? checks.every(Boolean) : undefined;
  }
}
