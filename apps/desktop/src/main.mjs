import { app, BrowserWindow, Menu, Tray, ipcMain, shell } from "electron";
import { spawn } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(__dirname, "..", "..", "..");
const stateDir = path.join(root, ".mia", "desktop");
const stateFile = path.join(stateDir, "state.json");
const dashboardUrl = process.env.MIA_DASHBOARD_URL || "http://localhost:3000";
const appUrl = `${dashboardUrl.replace(/\/$/, "")}/app`;

let mainWindow = null;
let tray = null;
let gateway = null;

function readState() {
  if (!existsSync(stateFile)) {
    return { connected: false, dashboardUrl, lastGatewayStart: null };
  }
  try {
    return JSON.parse(readFileSync(stateFile, "utf8"));
  } catch {
    return { connected: false, dashboardUrl, lastGatewayStart: null };
  }
}

function writeState(nextState) {
  mkdirSync(stateDir, { recursive: true });
  writeFileSync(stateFile, JSON.stringify(nextState, null, 2));
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1120,
    height: 720,
    minWidth: 900,
    minHeight: 560,
    title: "Mia",
    backgroundColor: "#111111",
    webPreferences: {
      preload: path.join(__dirname, "preload.mjs"),
    },
  });
  mainWindow.loadURL(appUrl);
  mainWindow.on("closed", () => {
    mainWindow = null;
  });
}

function startGateway() {
  if (gateway && gateway.exitCode === null) return;
  gateway = spawn("node", ["scripts/mia-gateway.mjs"], {
    cwd: root,
    env: { ...process.env },
    stdio: "ignore",
  });
  writeState({ ...readState(), connected: true, lastGatewayStart: Date.now() });
}

function stopGateway() {
  if (gateway && gateway.exitCode === null) {
    gateway.kill("SIGTERM");
  }
  gateway = null;
  writeState({ ...readState(), connected: false });
}

function buildMenu() {
  return Menu.buildFromTemplate([
    { label: "Open Mia", click: () => (mainWindow ? mainWindow.show() : createWindow()) },
    { label: "Open Website", click: () => shell.openExternal(dashboardUrl) },
    { label: "Open App", click: () => shell.openExternal(appUrl) },
    { type: "separator" },
    { label: "Start Local Gateway", click: startGateway },
    { label: "Stop Local Gateway", click: stopGateway },
    { type: "separator" },
    { label: "Quit", click: () => app.quit() },
  ]);
}

app.whenReady().then(() => {
  writeState(readState());
  createWindow();
  tray = new Tray(path.join(root, "apps", "dashboard", "public", "mia-logo.png"));
  tray.setToolTip("Mia");
  tray.setContextMenu(buildMenu());

  ipcMain.handle("mia:state", () => readState());
  ipcMain.handle("mia:startGateway", () => {
    startGateway();
    return readState();
  });
  ipcMain.handle("mia:stopGateway", () => {
    stopGateway();
    return readState();
  });
});

app.on("activate", () => {
  if (!mainWindow) createWindow();
});

app.on("before-quit", () => {
  stopGateway();
});
