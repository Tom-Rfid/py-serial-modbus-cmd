/**
 * Types du format Msg_*.json — identique à la version Python (docs/Francais/MESSAGES.md).
 */

export type IntType =
  | 'u8' | 'i8'
  | 'u16be' | 'u16le' | 'i16be' | 'i16le'
  | 'u32be' | 'u32le' | 'i32be' | 'i32le';

export type ParamType = IntType | 'bool' | 'enum' | 'hex' | 'raw' | 'ascii';

export type ChecksumAlgo = 'xor8' | 'sum8' | 'sum8_2c' | 'crc8' | 'crc16_modbus';

export type ParamValue = string | number | boolean;
export type ParamValues = Record<string, ParamValue>;

export interface ParamDef {
  type?: ParamType;            // défaut : u8
  label?: string;
  default?: ParamValue;
  min?: number | string;
  max?: number | string;
  unit?: string;
  choices?: Record<string, number>;   // enum
  size?: IntType;                     // enum, défaut u8
  length?: number;                    // ascii à longueur fixe
}

export interface ChecksumDef {
  algo?: ChecksumAlgo;         // défaut : xor8
  start?: number;              // défaut : 0
}

/**
 * Message « de protocole » (core/request_message.py) : la trame n'est pas décrite octet par
 * octet, elle est construite par le protocole en cours (Protocol.build) avec ces valeurs.
 */
export interface RequestDef {
  request_id?: number | string;
  command_id: number | string;
  /** DATA en hexa ("" = pas de données) */
  data?: string;
  /** autres champs d'en-tête, par nom ou rôle */
  header?: Record<string, number | string>;
  /** format de trame (protocole à variantes) */
  variant?: string;
}

export interface MessageDef {
  name: string;
  /** Morceaux de la trame ; [] pour un message de protocole (clé "request") */
  frame: string[];
  /** Message de protocole : trame construite par le protocole en cours */
  request?: RequestDef;
  description?: string;
  group?: string;
  params?: Record<string, ParamDef>;
  checksum?: ChecksumDef;
  /** Protocole(s) pour lesquels le fichier a été écrit (clé "protocol" du fichier, information). */
  protocol?: string | string[];
}

export interface MessageFile {
  group?: string;
  protocol?: string | string[];
  messages: MessageDef[];
}
