import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("miaDesktop", {
  isElectron: true,
  platform: process.platform,
  state: () => ipcRenderer.invoke("mia:state"),
  startGateway: () => ipcRenderer.invoke("mia:startGateway"),
  stopGateway: () => ipcRenderer.invoke("mia:stopGateway"),
  toggleWindow: () => ipcRenderer.invoke("mia:toggleWindow"),
  minimizeToTray: () => ipcRenderer.invoke("mia:minimizeToTray"),
});
