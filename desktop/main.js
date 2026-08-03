const {
  app,
  BrowserWindow,
  Menu,
  Tray,
  dialog,
  nativeImage,
  shell,
} = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const net = require("node:net");
const path = require("node:path");

let mainWindow = null;
let backendProcess = null;
let isQuitting = false;
let backendUrl = null;
let dataDirectory = null;
let tray = null;
let trayTimer = null;
let trayState = "idle"; // idle | recording | paused | transcribing | error
let latestJob = null;
let latestJobKey = "";
let quitConfirmed = false;
let settings = { exportDirectory: null };

function settingsPath() {
  return path.join(app.getPath("userData"), "settings.json");
}

function loadSettings() {
  try {
    settings = { ...settings, ...JSON.parse(fs.readFileSync(settingsPath(), "utf8")) };
  } catch {
    // First run or unreadable file: keep defaults.
  }
}

function saveSettings() {
  try {
    fs.writeFileSync(settingsPath(), `${JSON.stringify(settings, null, 2)}\n`);
  } catch {
    // Non-fatal: the choice just won't persist.
  }
}

// "transcript.txt" -> "transcript (2).txt" when the name is already taken.
function uniqueSavePath(directory, filename) {
  const extension = path.extname(filename);
  const stem = path.basename(filename, extension);
  let candidate = path.join(directory, filename);
  for (let n = 2; fs.existsSync(candidate); n += 1) {
    candidate = path.join(directory, `${stem} (${n})${extension}`);
  }
  return candidate;
}

function localizedMessage(ja, en) {
  return app.getLocale().toLowerCase().startsWith("ja") ? ja : en;
}

const TRAY_TEXT = {
  showWindow: ["ウィンドウを表示", "Show window"],
  startRecording: ["録音を開始", "Start recording"],
  pauseRecording: ["録音を一時停止", "Pause recording"],
  resumeRecording: ["録音を再開", "Resume recording"],
  stopRecording: ["停止して文字起こし", "Stop and transcribe"],
  openDataFolder: ["保存先フォルダを開く", "Open data folder"],
  latestJobNone: ["直近のジョブ: なし", "Latest job: none"],
  latestJobPrefix: ["直近のジョブ: ", "Latest job: "],
  autoLaunch: ["ログイン時に自動起動", "Start at login"],
  exportFolder: ["書き出し先フォルダ", "Export folder"],
  exportAskEveryTime: ["毎回ダイアログで選ぶ", "Ask every time"],
  exportChoose: ["フォルダを選ぶ...", "Choose folder..."],
  exportOpen: ["書き出し先を開く", "Open export folder"],
  exportReset: ["毎回選ぶに戻す", "Back to asking every time"],
  quit: ["終了", "Quit"],
  quitCancel: ["キャンセル", "Cancel"],
  quitConfirm: ["終了する", "Quit anyway"],
  quitWarningMessage: ["録音中です。", "A recording is in progress."],
  quitWarningDetail: [
    "終了すると録音は停止し、文字起こしされません。",
    "Quitting stops the recording without transcribing it.",
  ],
  stateIdle: ["待機中", "Idle"],
  stateRecording: ["録音中", "Recording"],
  statePaused: ["一時停止中", "Paused"],
  stateTranscribing: ["文字起こし中", "Transcribing"],
  stateError: ["エンジン停止", "Engine stopped"],
  jobActive: ["処理中", "processing"],
  jobCompleted: ["完了", "done"],
  jobFailed: ["失敗", "failed"],
};

function t(key) {
  return localizedMessage(...TRAY_TEXT[key]);
}

const ACTIVE_JOB_STATUSES = new Set([
  "queued",
  "loading_model",
  "transcribing",
  "finalizing",
]);

function stateLabel(state) {
  const key = `state${state.charAt(0).toUpperCase()}${state.slice(1)}`;
  return TRAY_TEXT[key] ? t(key) : state;
}

function jobStatusLabel(status) {
  if (ACTIVE_JOB_STATUSES.has(status)) return t("jobActive");
  if (status === "completed") return t("jobCompleted");
  if (status === "failed") return t("jobFailed");
  return status;
}

function formatElapsed(seconds) {
  const total = Math.floor(seconds);
  const minutes = String(Math.floor(total / 60)).padStart(2, "0");
  return `${minutes}:${String(total % 60).padStart(2, "0")}`;
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
  dataDirectory = path.join(app.getPath("userData"), "data");
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
  backendUrl = url;
  return url;
}

function trayIconFor(state) {
  const name =
    process.platform === "darwin" ? `${state}Template.png` : `${state}.png`;
  return nativeImage.createFromPath(
    path.join(__dirname, "assets", "tray", name),
  );
}

async function chooseExportDirectory() {
  const result = await dialog.showOpenDialog({
    title: t("exportFolder"),
    defaultPath: settings.exportDirectory || app.getPath("downloads"),
    properties: ["openDirectory", "createDirectory"],
  });
  if (result.canceled || !result.filePaths.length) return;
  settings.exportDirectory = result.filePaths[0];
  saveSettings();
  rebuildTrayMenu();
}

// With an export folder configured, downloads (TXT/SRT/VTT/JSON/SUMMARY)
// save there silently; otherwise Electron's default save dialog appears.
function installDownloadHandler(webSession) {
  webSession.on("will-download", (event, item) => {
    const directory = settings.exportDirectory;
    if (!directory) return;
    try {
      fs.mkdirSync(directory, { recursive: true });
      item.setSavePath(uniqueSavePath(directory, item.getFilename()));
    } catch {
      // Fall back to the default save dialog.
    }
  });
}

function showMainWindow() {
  if (!mainWindow) return;
  if (mainWindow.isMinimized()) mainWindow.restore();
  mainWindow.show();
  mainWindow.focus();
}

// The recorder (MediaRecorder + mic stream) lives in the renderer, so tray
// actions drive it by clicking the same buttons the user would.
function clickRecorderButton(selector) {
  mainWindow?.webContents
    .executeJavaScript(
      `document.querySelector(${JSON.stringify(selector)})?.click()`,
    )
    .catch(() => {});
}

function rebuildTrayMenu() {
  if (!tray) return;
  const recording = trayState === "recording" || trayState === "paused";
  const items = [
    { label: t("showWindow"), click: showMainWindow },
    { type: "separator" },
  ];
  if (recording) {
    items.push(
      {
        label: trayState === "paused" ? t("resumeRecording") : t("pauseRecording"),
        click: () => clickRecorderButton("#record-pause"),
      },
      {
        label: t("stopRecording"),
        click: () => clickRecorderButton("#record-toggle"),
      },
    );
  } else {
    items.push({
      label: t("startRecording"),
      enabled: trayState !== "error",
      click: () => {
        showMainWindow();
        clickRecorderButton("#record-toggle");
      },
    });
  }
  items.push(
    { type: "separator" },
    {
      label: latestJob
        ? `${t("latestJobPrefix")}${latestJob.filename}（${jobStatusLabel(latestJob.status)}）`
        : t("latestJobNone"),
      enabled: Boolean(latestJob),
      click: showMainWindow,
    },
    {
      label: t("openDataFolder"),
      enabled: Boolean(dataDirectory),
      click: () => shell.openPath(dataDirectory),
    },
    {
      label: t("exportFolder"),
      submenu: [
        {
          label: settings.exportDirectory || t("exportAskEveryTime"),
          enabled: false,
        },
        { type: "separator" },
        { label: t("exportChoose"), click: chooseExportDirectory },
        ...(settings.exportDirectory
          ? [
              {
                label: t("exportOpen"),
                click: () => shell.openPath(settings.exportDirectory),
              },
              {
                label: t("exportReset"),
                click: () => {
                  settings.exportDirectory = null;
                  saveSettings();
                  rebuildTrayMenu();
                },
              },
            ]
          : []),
      ],
    },
  );
  if (process.platform === "win32" || process.platform === "darwin") {
    items.push({
      label: t("autoLaunch"),
      type: "checkbox",
      checked: app.getLoginItemSettings().openAtLogin,
      click: (item) => app.setLoginItemSettings({ openAtLogin: item.checked }),
    });
  }
  items.push({ type: "separator" }, { label: t("quit"), click: () => app.quit() });
  tray.setContextMenu(Menu.buildFromTemplate(items));
}

function applyTrayState(nextState, elapsedSeconds) {
  if (!tray) return;
  let tooltip = `Local Transcriber — ${stateLabel(nextState)}`;
  if (nextState === "recording" || nextState === "paused") {
    tooltip += ` ${formatElapsed(elapsedSeconds)}`;
  }
  tray.setToolTip(tooltip);
  const jobKey = latestJob ? `${latestJob.id}:${latestJob.status}` : "";
  const jobChanged = jobKey !== latestJobKey;
  latestJobKey = jobKey;
  if (nextState !== trayState) {
    trayState = nextState;
    tray.setImage(trayIconFor(nextState));
    rebuildTrayMenu();
  } else if (jobChanged) {
    rebuildTrayMenu();
  }
}

async function pollBackendState() {
  let nextState = "idle";
  let elapsed = 0;
  try {
    const statusResponse = await fetch(`${backendUrl}/api/recording/status`);
    const status = await statusResponse.json();
    if (status.state === "recording" || status.state === "paused") {
      nextState = status.state;
      elapsed = status.elapsed_seconds || 0;
    } else {
      const jobsResponse = await fetch(`${backendUrl}/api/jobs`);
      const jobs = (await jobsResponse.json()).jobs || [];
      latestJob = jobs[0] || null;
      nextState = jobs.some((job) => ACTIVE_JOB_STATUSES.has(job.status))
        ? "transcribing"
        : "idle";
    }
  } catch {
    // Keep the previous state through transient poll failures; only show the
    // error shape once the backend process is actually gone.
    nextState =
      backendProcess && backendProcess.exitCode === null ? trayState : "error";
  }
  applyTrayState(nextState, elapsed);
}

function createTray() {
  tray = new Tray(trayIconFor("idle"));
  tray.setToolTip("Local Transcriber");
  rebuildTrayMenu();
  tray.on("click", () => {
    if (process.platform !== "darwin") showMainWindow();
  });
  trayTimer = setInterval(pollBackendState, 1000);
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
  // Closing the window hides it to the tray; the renderer (and any active
  // recording) keeps running. Quitting goes through the tray menu or Cmd+Q.
  mainWindow.on("close", (event) => {
    if (!isQuitting && tray) {
      event.preventDefault();
      mainWindow.hide();
    }
  });
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
    loadSettings();
    createWindow();
    installDownloadHandler(mainWindow.webContents.session);
    try {
      const url = await startBackend();
      await mainWindow.loadURL(url);
      createTray();
    } catch (error) {
      dialog.showErrorBox(
        "Local Transcriber",
        error instanceof Error ? error.message : String(error),
      );
      app.quit();
    }
  });

  app.on("activate", () => showMainWindow());
}

app.on("before-quit", (event) => {
  if (
    !quitConfirmed &&
    (trayState === "recording" || trayState === "paused")
  ) {
    event.preventDefault();
    const choice = dialog.showMessageBoxSync({
      type: "warning",
      buttons: [t("quitCancel"), t("quitConfirm")],
      defaultId: 0,
      cancelId: 0,
      title: "Local Transcriber",
      message: t("quitWarningMessage"),
      detail: t("quitWarningDetail"),
    });
    if (choice === 1) {
      quitConfirmed = true;
      app.quit();
    }
    return;
  }
  isQuitting = true;
  if (trayTimer) clearInterval(trayTimer);
  trayTimer = null;
  tray?.destroy();
  tray = null;
  stopBackend();
});

app.on("window-all-closed", () => {
  // With the tray active the app stays resident; without it (startup
  // failure), closing the window still quits.
  if (!tray && !isQuitting) app.quit();
});
