const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("node:child_process");
const net = require("node:net");
const path = require("node:path");

let mainWindow = null;
let backendProcess = null;
let isQuitting = false;

function localizedMessage(ja, en) {
  return app.getLocale().toLowerCase().startsWith("ja") ? ja : en;
}

function projectRoot() {
  return path.resolve(__dirname, "..");
}

function findAvailablePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.unref();
    server.on("error", reject);
    server.listen(0, "127.0.0.1", () => {
      const address = server.address();
      server.close(() => resolve(address.port));
    });
  });
}

function backendCommand(port) {
  if (app.isPackaged) {
    const backendDirectory = path.join(
      process.resourcesPath,
      "local-transcriber-backend",
    );
    return {
      executable: path.join(
        backendDirectory,
        process.platform === "win32"
          ? "local-transcriber-backend.exe"
          : "local-transcriber-backend",
      ),
      args: ["--port", String(port)],
      cwd: backendDirectory,
    };
  }

  const root = projectRoot();
  const python =
    process.platform === "win32"
      ? path.join(root, ".venv", "Scripts", "python.exe")
      : path.join(root, ".venv", "bin", "python3");
  return {
    executable: python,
    args: [path.join(root, "app", "desktop.py"), "--port", String(port)],
    cwd: root,
  };
}

function normalizedEnvironment(overrides) {
  if (process.platform !== "win32") {
    return { ...process.env, ...overrides };
  }

  const values = new Map();
  for (const [key, value] of Object.entries(process.env)) {
    values.set(key.toUpperCase(), [key, value]);
  }
  for (const [key, value] of Object.entries(overrides)) {
    values.set(key.toUpperCase(), [key, value]);
  }
  return Object.fromEntries(values.values());
}

async function waitForBackend(url) {
  for (let attempt = 0; attempt < 120; attempt += 1) {
    if (backendProcess?.exitCode !== null) {
      throw new Error(localizedMessage(
        "文字起こしエンジンを起動できませんでした。",
        "The transcription engine could not be started.",
      ));
    }
    try {
      const response = await fetch(`${url}/api/health`);
      if (response.ok) return;
    } catch {
      // The backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(localizedMessage(
    "文字起こしエンジンの起動がタイムアウトしました。",
    "The transcription engine timed out while starting.",
  ));
}

async function startBackend() {
  const port = await findAvailablePort();
  const url = `http://127.0.0.1:${port}`;
  const command = backendCommand(port);
  const dataDirectory = path.join(app.getPath("userData"), "data");

  backendProcess = spawn(command.executable, command.args, {
    cwd: command.cwd,
    windowsHide: true,
    stdio: "ignore",
    env: normalizedEnvironment({
      PYTHONUTF8: "1",
      HF_HUB_DISABLE_SYMLINKS_WARNING: "1",
      TRANSCRIBER_DATA_DIR: dataDirectory,
      WHISPER_MODEL_DIR: path.join(dataDirectory, "models"),
    }),
  });
  await waitForBackend(url);
  return url;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1180,
    height: 820,
    minWidth: 820,
    minHeight: 620,
    show: false,
    autoHideMenuBar: true,
    backgroundColor: "#f4f3fb",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: true,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (url.startsWith("https://")) shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!url.startsWith("http://127.0.0.1:")) event.preventDefault();
  });
  mainWindow.once("ready-to-show", () => mainWindow.show());
}

function stopBackend() {
  if (backendProcess && backendProcess.exitCode === null) {
    backendProcess.kill();
  }
  backendProcess = null;
}

const lock = app.requestSingleInstanceLock();
if (!lock) {
  app.quit();
} else {
  app.on("second-instance", () => {
    if (mainWindow) {
      if (mainWindow.isMinimized()) mainWindow.restore();
      mainWindow.focus();
    }
  });

  app.whenReady().then(async () => {
    createWindow();
    try {
      const backendUrl = await startBackend();
      await mainWindow.loadURL(backendUrl);
    } catch (error) {
      dialog.showErrorBox(
        "Local Transcriber",
        error instanceof Error ? error.message : String(error),
      );
      app.quit();
    }
  });
}

app.on("before-quit", () => {
  isQuitting = true;
  stopBackend();
});

app.on("window-all-closed", () => {
  if (!isQuitting) app.quit();
});
