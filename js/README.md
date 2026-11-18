# serialhex (TypeScript)

Cœur de SerialHex en TypeScript : même format `Msg_*.json`, mêmes trames et même moteur de protocole (fichiers `protocols/*.json`) que la version Python, avec une intégration Electron et des hooks React.

```bash
npm install
npm test          # tests, dont les vecteurs partagés avec Python
npm run build     # dist/ : ESM + CommonJS + types
```

Documentation : [../docs/INTERFACE.md](../docs/INTERFACE.md)
