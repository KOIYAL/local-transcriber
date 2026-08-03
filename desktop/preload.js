// Bridges the served web UI to desktop-only features. Only present inside
// the Electron shell; the same UI in a plain browser sees no window.desktop.
const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("desktop", {
  getExportDirectory: () => ipcRenderer.invoke("export-directory:get"),
  chooseExportDirectory: () => ipcRenderer.invoke("export-directory:choose"),
  resetExportDirectory: () => ipcRenderer.invoke("export-directory:reset"),
});
