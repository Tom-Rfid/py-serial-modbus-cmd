import { describe, expect, it } from 'vitest';
import { classifyOpenError } from '../src/electron/errors';

describe('messages d\'erreur serialport', () => {
  it.each([
    ['Opening COM3: Access denied', 'busy'],
    ['Error Resource temporarily unavailable Cannot lock port', 'busy'],
    ['Opening COM9: File not found', 'missing'],
    ['Error: No such file or directory, cannot open /dev/ttyUSB0', 'missing'],
    ['Error: Permission denied, cannot open /dev/ttyUSB0', 'error'],
  ])('%s -> %s', (msg, status) => {
    expect(classifyOpenError(new Error(msg)).status).toBe(status);
  });
});
