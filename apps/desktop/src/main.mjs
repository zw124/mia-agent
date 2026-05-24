import { app, BrowserWindow, dialog, globalShortcut, Menu, Tray, ipcMain, screen } from "electron";
import { autoUpdater } from "electron-updater";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..", "..", "..");
const stateDir = path.join(root, ".mia", "desktop");
const stateFile = path.join(stateDir, "state.json");
const defaultDashboardPort = Number(process.env.MIA_DASHBOARD_PORT || "3000");

let mainWindow = null;
let tray = null;
let gateway = null;
let isQuitting = false;
let updateCheckStarted = false;

function gatewaySplashHtml(status = "Starting Mia…") {
  return `<!DOCTYPE html>
  <html lang="en">
    <head>
      <meta charset="utf-8" />
      <meta name="viewport" content="width=device-width, initial-scale=1" />
      <title>Mia</title>
      <style>
        :root {
          color-scheme: dark;
          font-family: "Geist Mono", "SF Mono", SFMono-Regular, ui-monospace, monospace;
        }
        * { box-sizing: border-box; }
        body {
          margin: 0;
          min-height: 100vh;
          display: flex;
          align-items: center;
          justify-content: center;
          background:
            radial-gradient(circle at 50% 42%, rgba(216, 255, 145, 0.08), transparent 24%),
            #0b0b0c;
          color: #e8e6df;
        }
        .shell {
          width: min(620px, calc(100vw - 56px));
        }
        .eyebrow {
          display: inline-flex;
          gap: 10px;
          align-items: center;
          margin-bottom: 20px;
          color: #7f7d76;
          font-size: 12px;
          letter-spacing: 0.08em;
          text-transform: uppercase;
        }
        .mark {
          width: 9px;
          height: 9px;
          border-radius: 999px;
          background: #d8ff91;
          box-shadow: 0 0 28px rgba(216,255,145,0.28);
        }
        h1 {
          margin: 0;
          color: #f4f2eb;
          font-size: clamp(34px, 5vw, 58px);
          font-weight: 500;
          line-height: 1.05;
          letter-spacing: -0.06em;
        }
        p {
          max-width: 520px;
          margin: 22px 0 0;
          font-size: 14px;
          line-height: 1.8;
          color: #8c8980;
        }
        .status {
          position: relative;
          margin-top: 34px;
          padding-left: 22px;
          font-size: 13px;
          color: #cbc8bf;
        }
        .status::before {
          content: "";
          position: absolute;
          left: 4px;
          top: 3px;
          bottom: 3px;
          width: 1px;
          background: rgba(216,255,145,0.34);
        }
      </style>
    </head>
    <body>
      <main class="shell">
        <div class="eyebrow"><span class="mark"></span><span>Mia desktop</span></div>
        <h1>Starting local runtime</h1>
        <p>Mia is starting the dashboard and local agent service. The workspace will open inside this desktop app when the runtime is ready.</p>
        <div class="status">${status}</div>
      </main>
    </body>
  </html>`;
}

function showSplash(status) {
  if (!mainWindow) return;
  mainWindow.loadURL(`data:text/html;charset=UTF-8,${encodeURIComponent(gatewaySplashHtml(status))}`).catch(() => {});
}

function currentDashboardUrl() {
  const state = readState();
  return String(state.dashboardUrl || `http://localhost:${defaultDashboardPort}`).replace(/\/$/, "");
}

function currentAppUrl() {
  return `${currentDashboardUrl()}/app`;
}

async function waitForDashboard(timeoutMs = 45000) {
  const appUrl = currentAppUrl();
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(appUrl, { method: "GET" });
      if (response.ok) return true;
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 1200));
  }
  return false;
}

function isPortTaken(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host: "127.0.0.1" });
    socket.setTimeout(400);
    socket.once("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.once("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.once("error", () => resolve(false));
  });
}

async function findAvailablePort(startPort) {
  for (let port = startPort; port < startPort + 20; port += 1) {
    // eslint-disable-next-line no-await-in-loop
    if (!(await isPortTaken(port))) return port;
  }
  return startPort;
}

function readState() {
  if (!existsSync(stateFile)) {
    return {
      connected: false,
      dashboardPort: defaultDashboardPort,
      dashboardUrl: `http://localhost:${defaultDashboardPort}`,
      lastGatewayStart: null,
      windowBounds: null,
    };
  }
  try {
    return JSON.parse(readFileSync(stateFile, "utf8"));
  } catch {
    return {
      connected: false,
      dashboardPort: defaultDashboardPort,
      dashboardUrl: `http://localhost:${defaultDashboardPort}`,
      lastGatewayStart: null,
      windowBounds: null,
    };
  }
}

function writeState(nextState) {
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(stateFile, JSON.stringify(nextState, null, 2));
}

function createWindow() {
  const state = readState();
  const { width: screenW, height: screenH } = screen.getPrimaryDisplay().workAreaSize;
  const defaultWidth = 1120;
  const defaultHeight = 720;
  const bounds = state.windowBounds || {
    x: Math.round((screenW - defaultWidth) / 2),
    y: Math.round((screenH - defaultHeight) / 2),
    width: defaultWidth,
    height: defaultHeight,
  };

  mainWindow = new BrowserWindow({
    x: bounds.x,
    y: bounds.y,
    width: bounds.width,
    height: bounds.height,
    minWidth: 900,
    minHeight: 560,
    title: "Mia",
    frame: false,
    titleBarStyle: "hidden",
    backgroundColor: "#0c0c0e",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
      nodeIntegration: false,
      contextIsolation: true,
    },
  });

  showSplash("Connecting to the local dashboard…");

  mainWindow.webContents.on("did-fail-load", (event, errorCode, errorDescription, validatedURL) => {
    const appUrl = currentAppUrl();
    // Retry loading when local server is still starting up (-102 is ERR_CONNECTION_REFUSED)
    if (validatedURL === appUrl && (errorCode === -102 || errorCode === -105 || errorCode === -106)) {
      showSplash(`Dashboard not reachable yet (${errorDescription}). Retrying…`);
      setTimeout(() => {
        if (mainWindow) {
          showSplash("Retrying dashboard connection…");
          bootDashboardWindow();
        }
      }, 1000);
    }
  });

  mainWindow.on("close", (event) => {
    if (!isQuitting) {
      event.preventDefault();
      mainWindow.hide();
    }
  });

  mainWindow.on("resize", () => {
    if (mainWindow && !mainWindow.isMinimized()) {
      const state = readState();
      writeState({ ...state, windowBounds: mainWindow.getBounds() });
    }
  });

  mainWindow.on("move", () => {
    if (mainWindow && !mainWindow.isMinimized()) {
      const state = readState();
      writeState({ ...state, windowBounds: mainWindow.getBounds() });
    }
  });

  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

async function bootDashboardWindow() {
  if (!mainWindow) return;
  showSplash("Waiting for local services to finish booting…");
  const ready = await waitForDashboard();
  const appUrl = currentAppUrl();
  if (!mainWindow) return;
  if (ready) {
    await mainWindow.loadURL(appUrl);
    return;
  }
  showSplash("Mia is still starting. Check your local dependencies if this screen does not clear.");
}

function toggleWindow() {
  if (!mainWindow) {
    createWindow();
    return;
  }
  if (mainWindow.isVisible()) {
    if (mainWindow.isFocused()) {
      mainWindow.hide();
    } else {
      mainWindow.show();
      mainWindow.focus();
    }
  } else {
    mainWindow.show();
    mainWindow.focus();
  }
}

async function startGateway() {
  if (gateway && gateway.exitCode === null) return;
  const dashboardPort = await findAvailablePort(defaultDashboardPort);
  const dashboardUrl = `http://localhost:${dashboardPort}`;
  gateway = spawn("node", ["scripts/mia-gateway.mjs", `--dashboard-port=${dashboardPort}`], {
    cwd: root,
    env: {
      ...process.env,
      MIA_DASHBOARD_PORT: String(dashboardPort),
      MIA_DASHBOARD_URL: dashboardUrl,
    },
    stdio: "ignore",
  });
  writeState({
    ...readState(),
    connected: true,
    dashboardPort,
    dashboardUrl,
    lastGatewayStart: Date.now(),
  });
}

function stopGateway() {
  if (gateway && gateway.exitCode === null) {
    gateway.kill("SIGTERM");
  }
  gateway = null;
  writeState({ ...readState(), connected: false });
}

function registerShortcuts() {
  globalShortcut.unregisterAll();

  globalShortcut.register("Alt+Space", () => {
    toggleWindow();
  });
}

function buildMenu() {
  return Menu.buildFromTemplate([
    {
      label: "Open Mia",
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
          void bootDashboardWindow();
        } else {
          createWindow();
          void bootDashboardWindow();
        }
      },
    },
    { type: "separator" },
    {
      label: "Toggle shortcut: ⌥ Space",
      enabled: false,
    },
    { type: "separator" },
    {
      label: "Start Local Gateway",
      click: () => {
        void startGateway();
      },
    },
    {
      label: "Stop Local Gateway",
      click: stopGateway,
    },
    { type: "separator" },
    {
      label: "Quit",
      click: () => {
        isQuitting = true;
        app.quit();
      },
    },
  ]);
}

function createTray() {
  const iconPath = path.join(root, "apps", "dashboard", "public", "mia-logo.png");
  tray = new Tray(iconPath);
  tray.setToolTip("Mia - Press ⌥ Space to toggle");
  tray.setContextMenu(buildMenu());

  tray.on("click", () => {
    toggleWindow();
  });
}

function setupAutoUpdates() {
  if (!app.isPackaged || updateCheckStarted) return;
  updateCheckStarted = true;
  autoUpdater.autoDownload = true;
  autoUpdater.autoInstallOnAppQuit = true;

  autoUpdater.on("update-downloaded", async () => {
    const result = await dialog.showMessageBox(mainWindow ?? undefined, {
      type: "info",
      buttons: ["Restart and install", "Later"],
      defaultId: 0,
      cancelId: 1,
      title: "Mia update ready",
      message: "A new Mia update has been downloaded.",
      detail: "Restart Mia to install it now, or install automatically when you quit the app.",
    });
    if (result.response === 0) {
      isQuitting = true;
      autoUpdater.quitAndInstall();
    }
  });

  setTimeout(() => {
    autoUpdater.checkForUpdatesAndNotify().catch(() => {});
  }, 5000);
}

app.whenReady().then(() => {
  writeState(readState());
  createWindow();
  createTray();
  registerShortcuts();
  setupAutoUpdates();

  // Automatically start gateway on launch if not running!
  void startGateway().then(() => bootDashboardWindow());

  ipcMain.handle("mia:state", () => readState());
  ipcMain.handle("mia:startGateway", async () => {
    await startGateway();
    return readState();
  });
  ipcMain.handle("mia:stopGateway", () => {
    stopGateway();
    return readState();
  });
  ipcMain.handle("mia:toggleWindow", () => {
    toggleWindow();
    return { visible: mainWindow?.isVisible() ?? false };
  });
  ipcMain.handle("mia:minimizeToTray", () => {
    if (mainWindow) mainWindow.hide();
    return {};
  });
});

app.on("will-quit", () => {
  globalShortcut.unregisterAll();
});

app.on("activate", () => {
  if (!mainWindow) createWindow();
  else { mainWindow.show(); mainWindow.focus(); }
});

app.on("before-quit", () => {
  isQuitting = true;
  stopGateway();
});
