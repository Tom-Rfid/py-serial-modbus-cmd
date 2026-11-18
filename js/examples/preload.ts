// Extrait du preload.ts de l'application Electron
import { exposeSerialHex } from 'serialhex/electron/preload';

exposeSerialHex(); // -> window.serialhex
