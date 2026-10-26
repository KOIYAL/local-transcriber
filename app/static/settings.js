// App settings strip at the bottom of the workspace.
//
// - Export folder row: desktop app only (needs window.desktop from preload).
// - Updates row: checks the app and model; upgrades require confirmation.

const SETTINGS_STRINGS = {
  en: {
    settingsTitle: "Settings",
    exportLabel: "Export folder",
    exportAsk: "Ask every time",
    exportChange: "Change",
    exportReset: "Ask again",
    modelLabel: "Transcription model",
    modelCheck: "Check for updates",
    updatesCurrent: "The app and model are up to date ({current}).",
    appUpdateConfirm: "New version {latest} is available. Open the download page?",
    appUpdateUnavailable: "App update check is disabled or unavailable (offline).",
    modelConfirm:
      "Switch from \"{current}\" to \"{recommended}\"? The download starts right away and transcription pauses until it finishes.",
    modelFailed: "The model check failed.",
  },
  ja: {
    settingsTitle: "設定",
    exportLabel: "書き出し先",
    exportAsk: "毎回ダイアログで選ぶ",
    exportChange: "変更",
    exportReset: "毎回選ぶに戻す",
    modelLabel: "文字起こしモデル",
    modelCheck: "アップデートを確認",
    updatesCurrent: "アプリもモデルも最新です（{current}）",
    appUpdateConfirm: "新しいバージョン {latest} があります。ダウンロードページを開きますか？",
    appUpdateUnavailable: "アプリの更新を確認できません（確認停止中、またはオフライン）。",
    modelConfirm:
      "「{current}」から「{recommended}」に切り替えますか？ダウンロードがすぐに始まり、完了するまで文字起こしは待機になります。",
    modelFailed: "モデルの確認に失敗しました。",
  },
};

const settingsSection = document.querySelector("#app-settings");

if (settingsSection) {
  const exportRow = document.querySelector("#export-row");
  const exportValue = document.querySelector("#export-value");
  const exportChange = document.querySelector("#export-change");
  const exportReset = document.querySelector("#export-reset");
  const modelValue = document.querySelector("#model-value");
  const modelCheck = document.querySelector("#model-check");

  const st = (key) => {
    const locale = window.LT?.getLocale?.() === "ja" ? "ja" : "en";
    return SETTINGS_STRINGS[locale][key] || SETTINGS_STRINGS.en[key] || key;
  };

  const renderExport = (directory) => {
    exportValue.textContent = directory || st("exportAsk");
    exportReset.hidden = !directory;
  };

  const localizeSettings = () => {
    document.querySelectorAll("[data-settings-i18n]").forEach((element) => {
      element.textContent = st(element.dataset.settingsI18n);
    });
    if (window.desktop) {
      window.desktop.getExportDirectory().then(renderExport);
    }
    refreshModel();
  };

  const refreshModel = async () => {
    try {
      const setup = await (await fetch("/api/setup")).json();
      modelValue.textContent = setup.model || "-";
    } catch {
      modelValue.textContent = "-";
    }
  };

  if (window.desktop) {
    exportChange.addEventListener("click", async () => {
      renderExport(await window.desktop.chooseExportDirectory());
    });
    exportReset.addEventListener("click", async () => {
      renderExport(await window.desktop.resetExportDirectory());
    });
  } else {
    exportRow.hidden = true;
  }

  modelCheck.addEventListener("click", async () => {
    if (modelCheck.disabled) return;
    modelCheck.disabled = true;
    let appCheck = null;
    try {
      try {
        const response = await fetch("/api/update-check?force=true");
        if (!response.ok) throw new Error("update_check_failed");
        appCheck = await response.json();
        const available = window.LT?.setAppUpdate(appCheck);
        if (!appCheck.checked) {
          window.LT?.showToast(st("appUpdateUnavailable"));
        } else if (available && window.confirm(st("appUpdateConfirm").replace("{latest}", appCheck.latest))) {
          // The desktop shell routes new HTTPS windows to the external browser.
          window.open(appCheck.url, "_blank", "noopener,noreferrer");
        }
      } catch {
        appCheck = null;
        window.LT?.showToast(st("appUpdateUnavailable"));
      }
      const modelResponse = await fetch("/api/models/upgrade-check");
      if (!modelResponse.ok) throw new Error("model_check_failed");
      const check = await modelResponse.json();
      if (!check.upgrade_available) {
        if (appCheck?.checked && !appCheck.update_available) {
          window.LT?.showToast(st("updatesCurrent").replace("{current}", appCheck.current));
        }
        return;
      }
      const message = st("modelConfirm")
        .replace("{current}", check.current)
        .replace("{recommended}", check.recommended);
      if (!window.confirm(message)) return;
      const response = await fetch("/api/models/upgrade", { method: "POST" });
      if (!response.ok) throw new Error("upgrade_failed");
      // Reload so the normal first-setup flow shows download progress.
      window.location.reload();
    } catch {
      window.LT?.showToast(st("modelFailed"));
    } finally {
      modelCheck.disabled = false;
    }
  });

  document.querySelectorAll("[data-locale]").forEach((button) => {
    button.addEventListener("click", () => localizeSettings());
  });
  localizeSettings();
}
