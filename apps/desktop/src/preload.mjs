import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("miaDesktop", {
  state: () => ipcRenderer.invoke("mia:state"),
  startGateway: () => ipcRenderer.invoke("mia:startGateway"),
  stopGateway: () => ipcRenderer.invoke("mia:stopGateway"),
});
