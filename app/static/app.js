const form = document.querySelector("#transcription-form");
const workspace = document.querySelector("#workspace");
const setupPanel = document.querySelector("#setup-panel");
const setupTitle = document.querySelector("#setup-title");
const setupDescription = document.querySelector("#setup-description");
const setupProgressBar = document.querySelector("#setup-progress-bar");
const setupMessage = document.querySelector("#setup-message");
const setupRetry = document.querySelector("#setup-retry");
const fileInput = document.querySelector("#file-input");
const dropZone = document.querySelector("#drop-zone");
const selectedFile = document.querySelector("#selected-file");
const fileName = document.querySelector("#file-name");
const fileSize = document.querySelector("#file-size");
const removeFileButton = document.querySelector("#remove-file");
const submitButton = document.querySelector("#submit-button");
const limitLabel = document.querySelector("#limit-label");
const progressPanel = document.querySelector("#progress-panel");
const progressTitle = document.querySelector("#progress-title");
const progressPercent = document.querySelector("#progress-percent");
const progressBar = document.querySelector("#progress-bar");
const progressMessage = document.querySelector("#progress-message");
const resultPanel = document.querySelector("#result-panel");
const resultMeta = document.querySelector("#result-meta");
const transcript = document.querySelector("#transcript");
const downloadButtons = document.querySelector("#download-buttons");
const copyButton = document.querySelector("#copy-button");
const toast = document.querySelector("#toast");
const localeButtons = document.querySelectorAll("[data-locale]");

const translations = {
  en: {
    appName: "Local Transcriber",
    localProcessing: "Local processing",
    heroTitle: "Turn audio and video<br><span>into text, privately.</span>",
    heroDescription:
      "Select a file and transcribe it entirely on this computer. No complicated setup or API key required.",
    setupTitle: "Preparing transcription",
    setupDescription:
      "The app is automatically selecting and downloading an AI model suited to this computer. The first setup may take a few minutes.",
    setupChecking: "Checking this computer.",
    setupStarting: "Starting first-time setup.",
    setupDownloading: "Downloading the transcription model.",
    setupReady: "Transcription is ready.",
    setupFailedTitle: "First-time setup failed",
    setupFailedDescription:
      "Check your internet connection, then try again.",
    setupFailedMessage: "The model could not be prepared.",
    retry: "Try again",
    selectFile: "Select a file",
    checkingLimit: "Checking limit...",
    fileLimit: "Audio and video / up to {{size}} MB",
    dropTitle: "Drop a file here",
    dropSubtitle: "or click to select audio or video",
    removeFile: "Remove file",
    startTranscription: "Start transcription",
    anotherFile: "Transcribe another file",
    uploading: "Uploading...",
    processing: "Processing...",
    preparingTranscription: "Preparing transcription",
    uploadingFile: "Uploading file.",
    transcriptionResult: "Transcription result",
    copyAll: "Copy all",
    featuresLabel: "Features",
    privateTitle: "Private",
    privateDescription:
      "Transcription stays on this computer. The temporary source copy is deleted after processing.",
    formatsTitle: "Multiple formats",
    formatsDescription:
      "Works with audio and video, with exports in TXT, SRT, VTT, and JSON.",
    automaticTitle: "Automatic setup",
    automaticDescription:
      "Automatically prepares an appropriate model based on the computer's memory.",
    poweredBy: "Powered by KOIYAL, K.K.",
    offlineAfterSetup: "Works offline after the first setup.",
    contactDescription:
      "Contact us through the website contact form or by DM on X.",
    contactLinksLabel: "Contact links",
    websiteLink: "Website",
    xLink: "X",
    statusQueued: "Waiting",
    statusLoadingModel: "Preparing model",
    statusTranscribing: "Transcribing",
    statusFinalizing: "Creating output",
    statusCompleted: "Complete",
    statusFailed: "Error",
    statusProcessing: "Processing",
    waitingForProcessing: "Waiting to start.",
    loadingModel: "Loading the transcription model.",
    analyzingAudio: "Analyzing audio.",
    transcribingProgress: "Transcribing: {{percent}}%",
    creatingOutput: "Creating output files.",
    transcriptionComplete: "Transcription complete.",
    transcriptionFailed: "Transcription failed.",
    processingFailed: "Processing failed",
    uploadFailed: "Upload failed",
    languageConfidence: "language confidence {{percent}}%",
    copied: "Transcription copied.",
    copyFailed: "Could not copy the transcription.",
    configFailed: "Could not load the app settings.",
    appStartFailed: "Could not start the app",
    genericError: "The operation failed.",
    fileTooLarge: "The file limit is {{size}} MB.",
    errorUnsupportedExtension:
      "This file type is not supported. Supported types: {{allowed}}",
    errorSetupIncomplete: "Wait for the first-time setup to finish.",
    errorEmptyFile: "The selected file is empty.",
    errorJobNotFound: "The transcription job could not be found.",
    errorJobIncomplete: "Processing is not complete.",
    errorOutputMissing: "The output file could not be found.",
    errorJobBusy: "The job is still processing or could not be found.",
  },
  ja: {
    appName: "文字起こし",
    localProcessing: "ローカル処理",
    heroTitle: "音声と動画を、<br><span>手元で文字に。</span>",
    heroDescription:
      "ファイルを選ぶだけで、この端末上で文字起こしします。難しい設定やAPIキーは必要ありません。",
    setupTitle: "文字起こしの準備をしています",
    setupDescription:
      "この端末に適したAIモデルを自動で選び、ダウンロードしています。初回だけ数分かかることがあります。",
    setupChecking: "端末の構成を確認しています。",
    setupStarting: "初回セットアップを開始します。",
    setupDownloading: "文字起こしモデルをダウンロードしています。",
    setupReady: "文字起こしの準備ができました。",
    setupFailedTitle: "初回セットアップに失敗しました",
    setupFailedDescription:
      "インターネット接続を確認して、もう一度お試しください。",
    setupFailedMessage: "モデルを準備できませんでした。",
    retry: "もう一度試す",
    selectFile: "ファイルを選択",
    checkingLimit: "上限を確認中...",
    fileLimit: "音声・動画 / 最大 {{size}} MB",
    dropTitle: "ここにファイルをドロップ",
    dropSubtitle: "またはクリックして音声・動画を選択",
    removeFile: "ファイルを外す",
    startTranscription: "文字起こしを開始",
    anotherFile: "別のファイルを文字起こし",
    uploading: "アップロード中...",
    processing: "処理中...",
    preparingTranscription: "文字起こしを準備中",
    uploadingFile: "ファイルをアップロードしています。",
    transcriptionResult: "文字起こし結果",
    copyAll: "全文をコピー",
    featuresLabel: "サービスの特徴",
    privateTitle: "プライベート",
    privateDescription:
      "推論処理はこの端末内で完結。処理後の元ファイルは自動削除されます。",
    formatsTitle: "複数形式",
    formatsDescription:
      "音声・動画に対応し、TXT、SRT、VTT、JSONとして書き出せます。",
    automaticTitle: "自動セットアップ",
    automaticDescription:
      "端末のメモリに合わせて、適切なモデルを自動で準備します。",
    poweredBy: "Powered by 株式会社KOIYAL",
    offlineAfterSetup: "初回セットアップ後はオフラインでも利用できます。",
    contactDescription:
      "お問い合わせはウェブサイトのお問い合わせフォーム、またはXのDMで受け付けています。",
    contactLinksLabel: "お問い合わせリンク",
    websiteLink: "ウェブサイト",
    xLink: "X",
    statusQueued: "処理待ち",
    statusLoadingModel: "モデルを準備中",
    statusTranscribing: "文字起こし中",
    statusFinalizing: "出力を作成中",
    statusCompleted: "完了",
    statusFailed: "エラー",
    statusProcessing: "処理中",
    waitingForProcessing: "処理開始を待っています。",
    loadingModel: "文字起こしモデルを読み込んでいます。",
    analyzingAudio: "音声を解析しています。",
    transcribingProgress: "文字起こし中: {{percent}}%",
    creatingOutput: "出力ファイルを作成しています。",
    transcriptionComplete: "文字起こしが完了しました。",
    transcriptionFailed: "文字起こしに失敗しました。",
    processingFailed: "処理に失敗しました",
    uploadFailed: "アップロードに失敗しました",
    languageConfidence: "言語確度 {{percent}}%",
    copied: "文字起こし結果をコピーしました。",
    copyFailed: "コピーできませんでした。",
    configFailed: "設定を取得できませんでした。",
    appStartFailed: "アプリを開始できませんでした",
    genericError: "処理に失敗しました。",
    fileTooLarge: "ファイル上限は {{size}} MB です。",
    errorUnsupportedExtension:
      "未対応のファイル形式です。対応形式: {{allowed}}",
    errorSetupIncomplete: "初回セットアップが完了するまでお待ちください。",
    errorEmptyFile: "選択されたファイルは空です。",
    errorJobNotFound: "ジョブが見つかりません。",
    errorJobIncomplete: "処理が完了していません。",
    errorOutputMissing: "出力ファイルがありません。",
    errorJobBusy: "処理中か、ジョブが見つかりません。",
  },
};

const statusTitleKeys = {
  queued: "statusQueued",
  loading_model: "statusLoadingModel",
  transcribing: "statusTranscribing",
  finalizing: "statusFinalizing",
  completed: "statusCompleted",
  failed: "statusFailed",
};

const errorCodeKeys = {
  unsupported_extension: "errorUnsupportedExtension",
  setup_incomplete: "errorSetupIncomplete",
  file_too_large: "fileTooLarge",
  empty_file: "errorEmptyFile",
  job_not_found: "errorJobNotFound",
  job_incomplete: "errorJobIncomplete",
  output_missing: "errorOutputMissing",
  job_busy: "errorJobBusy",
};

let config = null;
let currentFile = null;
let currentJob = null;
let currentSetup = null;
let currentLocale = getInitialLocale();
let submitState = "startTranscription";
let pollTimer = null;
let setupTimer = null;
let toastTimer = null;

function getInitialLocale() {
  try {
    const stored = localStorage.getItem("local-transcriber-locale");
    if (stored === "ja" || stored === "en") return stored;
  } catch {
    // Use the operating system language when storage is unavailable.
  }
  return navigator.language.toLowerCase().startsWith("ja") ? "ja" : "en";
}

function t(key, params = {}) {
  const template = translations[currentLocale][key] || translations.en[key] || key;
  return template.replace(/\{\{(\w+)\}\}/g, (_, name) => String(params[name] ?? ""));
}

function setSubmitState(state) {
  submitState = state;
  submitButton.querySelector("span").textContent = t(state);
}

function applyLanguage(locale, persist = true) {
  currentLocale = locale === "ja" ? "ja" : "en";
  document.documentElement.lang = currentLocale;
  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-html]").forEach((element) => {
    element.innerHTML = t(element.dataset.i18nHtml);
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
  localeButtons.forEach((button) => {
    button.setAttribute(
      "aria-pressed",
      String(button.dataset.locale === currentLocale),
    );
  });
  if (persist) {
    try {
      localStorage.setItem("local-transcriber-locale", currentLocale);
    } catch {
      // Language selection still works for this session.
    }
  }
  if (config) updateLimitLabel();
  if (currentSetup) renderSetup(currentSetup);
  if (currentJob?.status === "completed") updateResultMeta(currentJob);
  else if (currentJob) updateProgress(currentJob);
  setSubmitState(submitState);
}

function showToast(message) {
  toast.textContent = message;
  toast.hidden = false;
  window.clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => {
    toast.hidden = true;
  }, 4200);
}

function formatBytes(bytes) {
  if (bytes === 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), 3);
  const value = bytes / (1024 ** index);
  return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatTime(seconds) {
  const totalSeconds = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const secs = totalSeconds % 60;
  if (hours > 0) {
    return `${String(hours).padStart(2, "0")}:${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
  }
  return `${String(minutes).padStart(2, "0")}:${String(secs).padStart(2, "0")}`;
}

function updateLimitLabel() {
  limitLabel.textContent = t("fileLimit", { size: config.max_upload_mb });
}

function setFile(file) {
  if (!file) {
    currentFile = null;
    fileInput.value = "";
    selectedFile.hidden = true;
    dropZone.hidden = false;
    submitButton.disabled = true;
    return;
  }
  if (config && file.size > config.max_upload_mb * 1024 * 1024) {
    showToast(t("fileTooLarge", { size: config.max_upload_mb }));
    return;
  }
  currentFile = file;
  fileName.textContent = file.name;
  fileSize.textContent = formatBytes(file.size);
  dropZone.hidden = true;
  selectedFile.hidden = false;
  submitButton.disabled = false;
  setSubmitState(currentJob?.status === "completed" ? "anotherFile" : "startTranscription");
}

async function loadConfig() {
  const response = await fetch("/api/config");
  if (!response.ok) throw new Error(t("configFailed"));
  config = await response.json();
  updateLimitLabel();
}

function renderSetup(setup) {
  currentSetup = setup;
  const percentage = Math.round((setup.progress || 0) * 100);
  setupProgressBar.style.width = `${percentage}%`;
  setupRetry.hidden = setup.status !== "failed";

  if (setup.ready) {
    setupMessage.textContent = t("setupReady");
    setupPanel.hidden = true;
    workspace.hidden = false;
    return;
  }

  setupPanel.hidden = false;
  workspace.hidden = true;
  if (setup.status === "failed") {
    setupTitle.textContent = t("setupFailedTitle");
    setupDescription.textContent = t("setupFailedDescription");
    setupMessage.textContent = setup.error
      ? `${t("setupFailedMessage")} ${setup.error}`
      : t("setupFailedMessage");
    return;
  }

  setupTitle.textContent = t("setupTitle");
  setupDescription.textContent = t("setupDescription");
  setupMessage.textContent =
    setup.status === "downloading" ? t("setupDownloading") : t("setupStarting");
}

async function checkSetup(retry = false) {
  window.clearTimeout(setupTimer);
  const response = await fetch(retry ? "/api/setup/retry" : "/api/setup", {
    method: retry ? "POST" : "GET",
  });
  if (!response.ok) throw new Error(await readError(response));
  const setup = await response.json();
  renderSetup(setup);
  if (!setup.ready && setup.status !== "failed") {
    setupTimer = window.setTimeout(() => checkSetup(false), 900);
  }
}

async function readError(response) {
  try {
    const payload = await response.json();
    if (Array.isArray(payload.detail)) {
      return payload.detail.map((item) => item.msg).join(" / ");
    }
    if (payload.detail && typeof payload.detail === "object") {
      const key = errorCodeKeys[payload.detail.code];
      if (key) return t(key, payload.detail.params || {});
    }
    return payload.detail || t("genericError");
  } catch {
    return t("genericError");
  }
}

function jobMessage(job) {
  if (job.status === "queued") return t("waitingForProcessing");
  if (job.status === "loading_model") return t("loadingModel");
  if (job.status === "transcribing") {
    if ((job.progress || 0) <= 0.13) return t("analyzingAudio");
    const percent = Math.max(
      1,
      Math.min(100, Math.round(((job.progress - 0.12) / 0.78) * 100)),
    );
    return t("transcribingProgress", { percent });
  }
  if (job.status === "finalizing") return t("creatingOutput");
  if (job.status === "completed") return t("transcriptionComplete");
  if (job.status === "failed") return t("transcriptionFailed");
  return t("waitingForProcessing");
}

function updateProgress(job) {
  const percentage = Math.round((job.progress || 0) * 100);
  progressTitle.textContent = t(statusTitleKeys[job.status] || "statusProcessing");
  progressPercent.textContent = `${percentage}%`;
  progressBar.style.width = `${percentage}%`;
  progressMessage.textContent = jobMessage(job);
}

function updateResultMeta(job) {
  const result = job.result;
  const probability = result.language_probability
    ? ` / ${t("languageConfidence", {
        percent: Math.round(result.language_probability * 100),
      })}`
    : "";
  const device = result.device ? ` / ${result.device.toUpperCase()}` : "";
  resultMeta.textContent =
    `${job.filename} / ${formatTime(result.duration)} / ${result.language}${device}${probability}`;
}

function renderResult(job) {
  currentJob = job;
  progressPanel.hidden = true;
  resultPanel.hidden = false;
  updateResultMeta(job);

  transcript.replaceChildren(
    ...job.result.segments.map((segment) => {
      const row = document.createElement("div");
      row.className = "segment";

      const time = document.createElement("span");
      time.className = "timestamp";
      time.textContent = `${formatTime(segment.start)} - ${formatTime(segment.end)}`;

      const text = document.createElement("p");
      text.textContent = segment.text;
      row.append(time, text);
      return row;
    }),
  );

  downloadButtons.replaceChildren(
    ...Object.entries(job.downloads || {}).map(([format, url]) => {
      const link = document.createElement("a");
      link.className = "download-button";
      link.href = url;
      link.textContent = format.toUpperCase();
      return link;
    }),
  );
  setFile(null);
  setSubmitState("anotherFile");
  resultPanel.scrollIntoView({ behavior: "smooth", block: "start" });
}

async function pollJob(jobId) {
  window.clearTimeout(pollTimer);
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) throw new Error(await readError(response));
    const job = await response.json();
    currentJob = job;
    updateProgress(job);

    if (job.status === "completed") {
      renderResult(job);
      return;
    }
    if (job.status === "failed") {
      throw new Error(job.error || t("transcriptionFailed"));
    }
    pollTimer = window.setTimeout(() => pollJob(jobId), 1000);
  } catch (error) {
    const message = error instanceof Error ? error.message : t("genericError");
    progressTitle.textContent = t("processingFailed");
    progressMessage.textContent = message;
    progressBar.style.background = "#b44732";
    submitButton.disabled = false;
    setSubmitState("startTranscription");
    showToast(message);
  }
}

localeButtons.forEach((button) => {
  button.addEventListener("click", () => applyLanguage(button.dataset.locale));
});
fileInput.addEventListener("change", () => setFile(fileInput.files[0]));
removeFileButton.addEventListener("click", () => setFile(null));
setupRetry.addEventListener("click", () => {
  setupRetry.hidden = true;
  currentSetup = { status: "not_started", progress: 0, ready: false };
  renderSetup(currentSetup);
  checkSetup(true).catch((error) => showToast(error.message));
});

for (const eventName of ["dragenter", "dragover"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.add("is-dragging");
  });
}

for (const eventName of ["dragleave", "drop"]) {
  dropZone.addEventListener(eventName, (event) => {
    event.preventDefault();
    dropZone.classList.remove("is-dragging");
  });
}

dropZone.addEventListener("drop", (event) => {
  setFile(event.dataTransfer.files[0]);
});

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!currentFile) return;

  submitButton.disabled = true;
  setSubmitState("uploading");
  resultPanel.hidden = true;
  progressPanel.hidden = false;
  progressBar.style.background = "";
  currentJob = {
    status: "queued",
    progress: 0.02,
  };
  updateProgress(currentJob);
  progressMessage.textContent = t("uploadingFile");
  progressPanel.scrollIntoView({ behavior: "smooth", block: "center" });

  const formData = new FormData(form);
  formData.set("file", currentFile);
  formData.set("vad_filter", "true");

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) throw new Error(await readError(response));
    const job = await response.json();
    currentJob = job;
    setSubmitState("processing");
    await pollJob(job.id);
  } catch (error) {
    const message = error instanceof Error ? error.message : t("genericError");
    progressTitle.textContent = t("uploadFailed");
    progressMessage.textContent = message;
    submitButton.disabled = false;
    setSubmitState("startTranscription");
    showToast(message);
  }
});

copyButton.addEventListener("click", async () => {
  const text = currentJob?.result?.text || "";
  if (!text) return;
  try {
    await navigator.clipboard.writeText(text);
    showToast(t("copied"));
  } catch {
    showToast(t("copyFailed"));
  }
});

applyLanguage(currentLocale, false);
loadConfig()
  .then(() => checkSetup(false))
  .catch((error) => {
    setupTitle.textContent = t("appStartFailed");
    setupMessage.textContent = error.message;
    showToast(error.message);
  });
