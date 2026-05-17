# Mia Desktop

Mia Desktop is the installable companion for the web control center.

It ships as an Electron app so the same code can be packaged for macOS, Windows, and Linux. On macOS it exposes a tray menu that can start or stop the local Mia gateway, then opens the same authenticated web console used by the deployed site.

## Development

```bash
npm install
npm run desktop:dev
```

## Package

```bash
npm run desktop:package
```

Artifacts are written to `apps/desktop/release`.

## First Run Model

The desktop app starts from the web console URL in `MIA_DASHBOARD_URL`, defaulting to `http://localhost:3000`. It stores local desktop state in `.mia/desktop/state.json` and launches `scripts/mia-gateway.mjs` from the repository root.
