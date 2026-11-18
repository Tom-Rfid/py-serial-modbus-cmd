import { defineConfig } from 'tsup';

export default defineConfig({
  entry: {
    index: 'src/index.ts',
    'react/index': 'src/react/index.ts',
    'electron/main': 'src/electron/main.ts',
    'electron/preload': 'src/electron/preload.ts',
  },
  format: ['esm', 'cjs'],
  dts: true,
  clean: true,
  sourcemap: true,
  external: ['electron', 'serialport', 'react'],
});
