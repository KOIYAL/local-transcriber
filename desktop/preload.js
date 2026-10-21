// Bridges the served web UI to desktop-only features. Only present inside
// the Electron shell; the same UI in a plain browser sees no window.desktop.
const { contextBridge, ipcRenderer } = require("electron");

const systemAudioPolicy = process.argv.find((arg) => arg.startsWith("--lt-system-audio="))
  ?.split("=")[1] || "unsupported-os";
contextBridge.exposeInMainWorld("localTranscriber", {
  settings: {
    get: (key) => ipcRenderer.sendSync("settings:get", key),
    set: (key, value) => ipcRenderer.sendSync("settings:set", key, value),
  },
  systemAudio: {
    supported: systemAudioPolicy === "supported",
    reason: systemAudioPolicy === "supported" ? "" : systemAudioPolicy,
  },
});

contextBridge.exposeInMainWorld("desktop", {
  getExportDirectory: () => ipcRenderer.invoke("export-directory:get"),
  chooseExportDirectory: () => ipcRenderer.invoke("export-directory:choose"),
  resetExportDirectory: () => ipcRenderer.invoke("export-directory:reset"),
});
