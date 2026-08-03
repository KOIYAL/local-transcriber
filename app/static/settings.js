// App settings strip at the bottom of the workspace.
//
// - Export folder row: desktop app only (needs window.desktop from preload).
// - Model row: works everywhere; upgrades only happen when the user asks.

const SETTINGS_STRINGS = {
  en: {
    settingsTitle: "Settings",
    exportLabel: "Export folder",
    exportAsk: "Ask every time",
    exportChange: "Change",
    exportReset: "Ask again",
    modelLabel: "Transcription model",
    modelCheck: "Check for a better model",
    modelBest: "This computer is already using the best model for its memory.",
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
    modelCheck: "より良いモデルを確認",
    modelBest: "このPCのメモリでは、すでに最適なモデルを使っています。",
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
    modelCheck.disabled = true;
    try {
      const check = await (await fetch("/api/models/upgrade-check")).json();
      if (!check.upgrade_available) {
        window.LT?.showToast(st("modelBest"));
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
