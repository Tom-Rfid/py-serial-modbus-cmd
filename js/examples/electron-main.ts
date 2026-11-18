// Extrait du main.ts de l'application Electron
import path from 'node:path';
import { app, ipcMain } from 'electron';
import { registerSerialHexIpc } from 'serialhex/electron/main';

// En dev : dossier du projet ; une fois packagé : resources/<dossier> (voir extraResource dans forge.config)
const resource = (name: string) =>
  app.isPackaged ? path.join(process.resourcesPath, name) : path.join(app.getAppPath(), name);

registerSerialHexIpc(ipcMain, {
  messagesDir: resource('msgLibrary/msgManual'),   // Msg_*.json : messages seuls (onglet Manuel)
  protocolsDir: resource('protocols'),   // structure des trames (modbus_rtu.json...)
});
