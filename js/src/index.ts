/**
 * serialhex — cœur partagé avec la version Python.
 *
 *   serialhex                  trames, messages, SerialLink (navigateur, Node, Electron)
 *   serialhex/react            hooks React
 *   serialhex/electron/main    process principal Electron (serialport)
 *   serialhex/electron/preload preload Electron (window.serialhex)
 */
export * from './core/types';
export * from './core/frames';
export * from './core/messages';
export * from './core/framer';
export { parseJsonc, stripJsonComments } from './core/jsonc';
export * from './core/protocol';
export * from './link/types';
export * from './link/serialLink';
export { getSerialHexBridge, type SerialHexBridge } from './electron/renderer';
