// In-app microphone recording with optional local computer audio.
//
// Chunks are uploaded every few seconds while the meeting is still running, so
// a crash never loses more than the in-flight chunk. The finished recording
// joins the normal job pipeline via window.LT.trackJob (see app.js).

const RECORDER_STRINGS = {
  en: {
    orRecord: "Or record right here",
    recordTitle: "Record a meeting",
    recordPrivacy: "Audio stays on this computer. Nothing is sent online.",
    recordStart: "Start recording",
    recordStop: "Stop and transcribe",
    recordPause: "Pause",
    recordResume: "Resume",
    recordCancelLabel: "Discard recording",
    recordCancelConfirm: "Discard this recording? The audio will be deleted.",
    recordingLabel: "Recording",
    pausedLabel: "Paused",
    finishingLabel: "Finishing...",
    silenceWarning:
      "No sound is being picked up. Check the microphone and input device.",
    micDenied:
      "Microphone access was denied. Allow microphone use for this app and try again.",
    recorderUnsupported: "Recording is not supported in this environment.",
    recordFailed: "Recording failed.",
    uploadFailedWarning:
      "Saving audio to the engine failed. What was recorded so far is kept; stop the recording to transcribe it.",
    recordPartial: "Only the part recorded before the saving error will be transcribed.",
    recordRecovered: "An interrupted recording was found and is being transcribed.",
    micLabel: "Microphone",
    micDefault: "System default microphone",
    systemAudioLabel: "Also record computer audio (online meetings)",
    systemAudioHint: "Allow audio sharing when prompted. Video is not saved.",
    systemAudioActive: "Computer audio included",
    systemAudioDenied: "Computer audio sharing was canceled or denied. Recording with the microphone only.",
    systemAudioMissing: "The selected source has no audio. Recording with the microphone only. Next time, choose a tab/screen and enable audio sharing.",
    systemAudioFailed: "Computer audio could not be captured or mixed. Check the OS capture permissions. Recording with the microphone only.",
    systemAudioEnded: "Computer audio sharing ended. Recording continues with the microphone only.",
  },
  ja: {
    orRecord: "または、その場で録音",
    recordTitle: "会議を録音する",
    recordPrivacy: "音声はこのコンピュータの中だけで処理されます。外部には送信されません。",
    recordStart: "録音を開始",
    recordStop: "停止して文字起こし",
    recordPause: "一時停止",
    recordResume: "再開",
    recordCancelLabel: "録音を破棄",
    recordCancelConfirm: "この録音を破棄しますか？音声データは削除されます。",
    recordingLabel: "録音中",
    pausedLabel: "一時停止中",
    finishingLabel: "仕上げ中...",
    silenceWarning: "音が入っていません。マイクと入力デバイスを確認してください。",
    micDenied:
      "マイクの使用が許可されませんでした。このアプリのマイク利用を許可して、もう一度お試しください。",
    recorderUnsupported: "この環境では録音を利用できません。",
    recordFailed: "録音に失敗しました。",
    uploadFailedWarning:
      "音声の保存に失敗しました。ここまでの録音は残っています。停止すると文字起こしします。",
    recordPartial: "保存エラーより前に録音した部分だけを文字起こしします。",
    recordRecovered: "中断された録音が見つかったので、文字起こしを始めます。",
    micLabel: "マイク",
    micDefault: "システムのデフォルトのマイク",
    systemAudioLabel: "PC で再生中の音声も録る（オンライン会議用）",
    systemAudioHint: "許可の画面が出たら音声の共有も有効にしてください。映像は保存しません。",
    systemAudioActive: "PC 音声あり",
    systemAudioDenied: "PC 音声の共有がキャンセルされたか、許可されませんでした。マイクだけで録音します。",
    systemAudioMissing: "選んだ共有元に音声がありません。マイクだけで録音します。次回はタブや画面を選び、音声の共有も有効にしてください。",
    systemAudioFailed: "PC 音声の取得または合成に失敗しました。OS の収録権限を確認してください。マイクだけで録音します。",
    systemAudioEnded: "PC 音声の共有が終了しました。マイクだけで録音を続けます。",
  },
};

const recorderRoot = document.querySelector("#recorder");

if (recorderRoot) {
  const toggleButton = document.querySelector("#record-toggle");
  const toggleLabel = document.querySelector("#record-toggle-label");
  const pauseButton = document.querySelector("#record-pause");
  const cancelButton = document.querySelector("#record-cancel");
  const livePanel = document.querySelector("#recorder-live");
  const elapsedLabel = document.querySelector("#record-elapsed");
  const stateLabel = document.querySelector("#record-state-label");
  const levelBar = document.querySelector("#level-bar");
  const warningLabel = document.querySelector("#record-warning");

  let state = "idle"; // idle | recording | paused | stopping
  let sessionId = null;
  let mediaRecorder = null;
  let mediaStream = null;
  let microphoneStream = null;
  let displayStream = null;
  let mixedStream = null;
  let displaySource = null;
  let starting = false;
  let audioContext = null;
  let analyser = null;
  let currentLevel = 0;
  let uploadChain = Promise.resolve();
  let uploadFailed = false;
  let discarding = false;
  let elapsedTimer = null;
  let meterTimer = null;
  let startedAt = 0;
  let activeAccum = 0;
  let silenceWarned = false;

  const rt = (key) => {
    const locale = window.LT?.getLocale?.() === "ja" ? "ja" : "en";
    return RECORDER_STRINGS[locale][key] || RECORDER_STRINGS.en[key] || key;
  };

  const micSelect = document.querySelector("#mic-select");
  const MIC_STORAGE_KEY = "lt.mic-device-id";
  const SYSTEM_AUDIO_STORAGE_KEY = "lt.system-audio";
  const systemAudioToggle = document.querySelector("#system-audio-toggle");
  const desktopAudio = window.localTranscriber?.systemAudio;
  const systemAudioSupported = Boolean(
    navigator.mediaDevices?.getDisplayMedia && window.AudioContext
    && (desktopAudio ? desktopAudio.supported : !window.desktop),
  );
  document.querySelector("#system-audio-row").hidden = !systemAudioSupported;
  document.querySelector("#system-audio-hint").hidden = !systemAudioSupported;
  systemAudioToggle.checked = systemAudioSupported
    && window.LTPreferences.get(SYSTEM_AUDIO_STORAGE_KEY) === "true";
  const saveSystemAudioChoice = () => {
    window.LTPreferences.set(SYSTEM_AUDIO_STORAGE_KEY, String(systemAudioToggle.checked));
  };
  systemAudioToggle.addEventListener("change", saveSystemAudioChoice);

  const stopStream = (stream) => stream?.getTracks().forEach((track) => track.stop());
  const fallBackToMicrophone = (reason) => {
    displaySource?.disconnect();
    displaySource = null;
    stopStream(displayStream);
    displayStream = null;
    systemAudioToggle.checked = false;
    saveSystemAudioChoice();
    document.querySelector("#system-audio-active").hidden = true;
    window.LT?.showToast(rt(reason));
  };

  const captureComputerAudio = async () => {
    try {
      // Call before any other await so browser user activation is still valid.
      displayStream = await navigator.mediaDevices.getDisplayMedia({ audio: true, video: true });
      displayStream.getVideoTracks().forEach((track) => track.stop());
      const tracks = displayStream.getAudioTracks();
      if (!tracks.length || tracks.some((track) => track.readyState === "ended")) {
        fallBackToMicrophone("systemAudioMissing");
        return;
      }
      const capturedStream = displayStream;
      tracks.forEach((track) => track.addEventListener("ended", () => {
        if (displayStream === capturedStream) fallBackToMicrophone("systemAudioEnded");
      }, { once: true }));
    } catch (error) {
      fallBackToMicrophone(
        error?.name === "NotAllowedError" ? "systemAudioDenied" : "systemAudioFailed",
      );
    }
  };

  const refreshMicrophones = async () => {
    if (!navigator.mediaDevices?.enumerateDevices) {
      micSelect.closest(".mic-row").hidden = true;
      return;
    }
    const saved = window.LTPreferences.get(MIC_STORAGE_KEY) || "";
    const devices = await navigator.mediaDevices.enumerateDevices();
    const mics = devices.filter((device) => device.kind === "audioinput");
    const options = [{ id: "", label: rt("micDefault") }];
    // Device labels stay empty until the first permission grant; until then
    // only the default entry is offered.
    for (const [index, mic] of mics.entries()) {
      if (!mic.deviceId || mic.deviceId === "default") continue;
      options.push({
        id: mic.deviceId,
        label: mic.label || `${rt("micLabel")} ${index + 1}`,
      });
    }
    micSelect.replaceChildren(
      ...options.map(({ id, label }) => {
        const option = document.createElement("option");
        option.value = id;
        option.textContent = label;
        option.selected = id === saved;
        return option;
      }),
    );
  };

  micSelect.addEventListener("change", () => {
    window.LTPreferences.set(MIC_STORAGE_KEY, micSelect.value);
  });
  navigator.mediaDevices?.addEventListener?.("devicechange", refreshMicrophones);

  const microphoneConstraints = () => {
    const saved = window.LTPreferences.get(MIC_STORAGE_KEY);
    return saved ? { deviceId: { exact: saved } } : true;
  };

  const localize = () => {
    document.querySelectorAll("[data-recorder-i18n]").forEach((element) => {
      element.textContent = rt(element.dataset.recorderI18n);
    });
    cancelButton.setAttribute("aria-label", rt("recordCancelLabel"));
    refreshMicrophones();
    syncControls();
  };

  const formatElapsed = (seconds) => {
    const total = Math.floor(seconds);
    const minutes = String(Math.floor(total / 60)).padStart(2, "0");
    return `${minutes}:${String(total % 60).padStart(2, "0")}`;
  };

  const elapsedSeconds = () =>
    activeAccum + (state === "recording" ? (Date.now() - startedAt) / 1000 : 0);

  const syncControls = () => {
    toggleLabel.textContent = state === "idle" ? rt("recordStart") : rt("recordStop");
    toggleButton.classList.toggle("is-recording", state !== "idle");
    pauseButton.hidden = state === "idle";
    cancelButton.hidden = state === "idle";
    livePanel.hidden = state === "idle";
    micSelect.disabled = starting || state !== "idle";
    systemAudioToggle.disabled = starting || state !== "idle";
    pauseButton.disabled = state === "stopping";
    cancelButton.disabled = state === "stopping";
    document.querySelector("#system-audio-active").hidden = !displayStream || state === "idle";
    pauseButton.textContent = state === "paused" ? rt("recordResume") : rt("recordPause");
    stateLabel.textContent =
      state === "paused"
        ? rt("pausedLabel")
        : state === "stopping"
          ? rt("finishingLabel")
          : rt("recordingLabel");
    if (state === "idle") {
      warningLabel.hidden = true;
      levelBar.style.width = "0%";
      elapsedLabel.textContent = "00:00";
    }
  };

  const readErrorCode = async (response) => {
    try {
      const payload = await response.json();
      return payload?.detail?.code || "";
    } catch {
      return "";
    }
  };

  const releaseMedia = () => {
    window.clearInterval(elapsedTimer);
    window.clearInterval(meterTimer);
    stopStream(mediaStream);
    stopStream(microphoneStream);
    stopStream(displayStream);
    stopStream(mixedStream);
    audioContext?.close().catch(() => {});
    mediaStream = null;
    microphoneStream = null;
    displayStream = null;
    mixedStream = null;
    displaySource = null;
    audioContext = null;
    analyser = null;
    document.querySelector("#system-audio-active").hidden = true;
  };

  const resetLocalState = () => {
    releaseMedia();
    mediaRecorder = null;
    starting = false;
    sessionId = null;
    uploadChain = Promise.resolve();
    uploadFailed = false;
    discarding = false;
    silenceWarned = false;
    activeAccum = 0;
    currentLevel = 0;
    state = "idle";
    syncControls();
  };

  const measureLevel = () => {
    if (!analyser) return;
    const samples = new Float32Array(analyser.fftSize);
    analyser.getFloatTimeDomainData(samples);
    let sum = 0;
    for (const value of samples) sum += value * value;
    currentLevel = Math.sqrt(sum / samples.length);
    if (state === "recording") {
      levelBar.style.width = `${Math.min(100, Math.round(currentLevel * 300))}%`;
    }
  };

  // Free the backend's single recording slot; harmless when it is already
  // gone (404). Never throws.
  const releaseSession = async (targetSession) => {
    if (!targetSession) return;
    try {
      await fetch(`/api/recording/${targetSession}`, { method: "DELETE" });
    } catch {
      // Backend unreachable: nothing more to clean up from here.
    }
  };

  const CHUNK_ATTEMPTS = 3;

  // POST one chunk, retrying transient failures (network blip, 5xx). A 4xx
  // is final: the session is gone or the recording hit its size limit.
  const postChunk = async (targetSession, blob, level) => {
    let lastError = null;
    for (let attempt = 0; attempt < CHUNK_ATTEMPTS; attempt += 1) {
      try {
        const response = await fetch(`/api/recording/${targetSession}/chunk`, {
          method: "POST",
          headers: { "X-Audio-Level": level.toFixed(4) },
          body: blob,
        });
        if (response.ok) return response.json();
        lastError = new Error(await readErrorCode(response));
        if (response.status < 500) break;
      } catch (error) {
        lastError = error;
      }
      await new Promise((resolve) => setTimeout(resolve, 500 * (attempt + 1)));
    }
    throw lastError || new Error("upload_failed");
  };

  const uploadChunk = (blob) => {
    if (!sessionId || discarding || uploadFailed) return;
    const targetSession = sessionId;
    const level = currentLevel;
    // The chain never rejects: a failure is recorded in uploadFailed and
    // surfaced right away, while the meeting is still running.
    uploadChain = uploadChain.then(async () => {
      if (discarding || uploadFailed) return;
      try {
        const status = await postChunk(targetSession, blob, level);
        if (status.silence_warning && !silenceWarned) {
          silenceWarned = true;
          warningLabel.textContent = rt("silenceWarning");
          warningLabel.hidden = false;
        } else if (!status.silence_warning && silenceWarned) {
          silenceWarned = false;
          warningLabel.hidden = true;
        }
      } catch {
        // Later chunks would not decode without this one, so stop sending;
        // the backend keeps a valid prefix of the recording.
        uploadFailed = true;
        warningLabel.textContent = rt("uploadFailedWarning");
        warningLabel.hidden = false;
      }
    });
  };

  const startRecording = async () => {
    if (starting || state !== "idle") return;
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      window.LT?.showToast(rt("recorderUnsupported"));
      return;
    }
    toggleButton.disabled = true;
    starting = true;
    syncControls();
    if (systemAudioSupported && systemAudioToggle.checked) await captureComputerAudio();
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: microphoneConstraints(),
      });
    } catch (error) {
      if (error?.name === "OverconstrainedError") {
        // The saved microphone is gone (unplugged); fall back to the default.
        window.LTPreferences.set(MIC_STORAGE_KEY, null);
        try {
          mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
        } catch {
          resetLocalState();
          window.LT?.showToast(rt("micDenied"));
          toggleButton.disabled = false;
          return;
        }
        refreshMicrophones();
      } else {
        resetLocalState();
        window.LT?.showToast(rt("micDenied"));
        toggleButton.disabled = false;
        return;
      }
    }
    microphoneStream = mediaStream;
    refreshMicrophones();
    try {
      const mimeType = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4"].find(
        (candidate) => MediaRecorder.isTypeSupported(candidate),
      );
      const startForm = new FormData();
      startForm.set("mime", mimeType || "audio/webm");
      const response = await fetch("/api/recording/start", {
        method: "POST",
        body: startForm,
      });
      if (!response.ok) throw new Error(await readErrorCode(response));
      sessionId = (await response.json()).session_id;

      audioContext = new AudioContext();
      await audioContext.resume();
      if (displayStream) {
        let microphoneSource = null;
        try {
          const destination = audioContext.createMediaStreamDestination();
          mixedStream = destination.stream;
          microphoneSource = audioContext.createMediaStreamSource(microphoneStream);
          displaySource = audioContext.createMediaStreamSource(displayStream);
          microphoneSource.connect(destination);
          displaySource.connect(destination);
          mediaStream = mixedStream;
        } catch {
          microphoneSource?.disconnect();
          stopStream(mixedStream);
          mixedStream = null;
          mediaStream = microphoneStream;
          fallBackToMicrophone("systemAudioFailed");
        }
      }
      analyser = audioContext.createAnalyser();
      analyser.fftSize = 2048;
      audioContext.createMediaStreamSource(mediaStream).connect(analyser);

      mediaRecorder = new MediaRecorder(
        mediaStream,
        mimeType ? { mimeType } : undefined,
      );
      mediaRecorder.addEventListener("dataavailable", (event) => {
        if (event.data && event.data.size > 0) uploadChunk(event.data);
      });
      mediaRecorder.start(5000);

      state = "recording";
      startedAt = Date.now();
      activeAccum = 0;
      elapsedTimer = window.setInterval(() => {
        elapsedLabel.textContent = formatElapsed(elapsedSeconds());
      }, 500);
      meterTimer = window.setInterval(measureLevel, 200);
      syncControls();
    } catch (error) {
      // The backend session was opened before the local recorder failed
      // (AudioContext / MediaRecorder); release it or every later start
      // would be refused with recording_in_progress.
      releaseMedia();
      await releaseSession(sessionId);
      resetLocalState();
      window.LT?.showToast(rt("recordFailed"));
    } finally {
      starting = false;
      toggleButton.disabled = false;
      syncControls();
    }
  };

  const transcriptionForm = () => {
    const data = new FormData();
    data.set("glossary", window.LT?.getGlossary() || "");
    data.set("diarize", String(window.LT?.getDiarize?.() || false));
    return data;
  };

  const stopRecording = async () => {
    if (!mediaRecorder || !sessionId) return;
    const targetSession = sessionId;
    state = "stopping";
    syncControls();
    toggleButton.disabled = true;
    if (mediaRecorder.state !== "inactive") {
      const stopped = new Promise((resolve) => {
        mediaRecorder.addEventListener("stop", resolve, { once: true });
      });
      try {
        mediaRecorder.stop();
        await stopped;
      } catch {
        // Already inactive: the chunks that exist are all we will get.
      }
    }
    // Stop capture immediately; pending uploads may take time to finish.
    releaseMedia();
    await uploadChain;
    const partial = uploadFailed;
    try {
      // Even after an upload failure the backend holds a valid prefix of
      // the meeting; transcribing that beats throwing the recording away.
      const response = await fetch(`/api/recording/${targetSession}/stop`, {
        method: "POST",
        body: transcriptionForm(),
      });
      if (!response.ok) throw new Error(await readErrorCode(response));
      const job = await response.json();
      resetLocalState();
      if (partial) window.LT?.showToast(rt("recordPartial"));
      await window.LT?.trackJob(job);
    } catch {
      // stop failed (empty recording, backend error): make sure the slot
      // is free before giving up, otherwise the next start is refused.
      await releaseSession(targetSession);
      window.LT?.showToast(rt("recordFailed"));
      resetLocalState();
    } finally {
      toggleButton.disabled = false;
    }
  };

  // A session can outlive this page: a reload or renderer crash leaves it
  // open on the backend with its chunks safely on disk. Finish it (that is
  // what the chunking was for) instead of leaving it to block new ones.
  const recoverOrphanSession = async () => {
    try {
      const status = await (await fetch("/api/recording/status")).json();
      if (!status.session_id || status.state === "idle") return;
      const response = await fetch(`/api/recording/${status.session_id}/stop`, {
        method: "POST",
        body: transcriptionForm(),
      });
      if (!response.ok) {
        await releaseSession(status.session_id);
        return;
      }
      const job = await response.json();
      window.LT?.showToast(rt("recordRecovered"));
      await window.LT?.trackJob(job);
    } catch {
      // Backend not reachable yet; a later start reports any conflict.
    }
  };

  const togglePause = async () => {
    if (!mediaRecorder || !sessionId) return;
    if (state === "recording") {
      mediaRecorder.pause();
      activeAccum += (Date.now() - startedAt) / 1000;
      state = "paused";
      await fetch(`/api/recording/${sessionId}/pause`, { method: "POST" });
    } else if (state === "paused") {
      mediaRecorder.resume();
      startedAt = Date.now();
      state = "recording";
      await fetch(`/api/recording/${sessionId}/resume`, { method: "POST" });
    }
    syncControls();
  };

  const cancelRecording = async () => {
    if (!sessionId || !window.confirm(rt("recordCancelConfirm"))) return;
    discarding = true;
    const targetSession = sessionId;
    state = "stopping";
    syncControls();
    toggleButton.disabled = true;
    try {
      mediaRecorder?.stop();
    } catch {
      // The recorder may already be inactive; deletion below still applies.
    }
    releaseMedia();
    try {
      await releaseSession(targetSession);
    } finally {
      resetLocalState();
      toggleButton.disabled = false;
    }
  };

  toggleButton.addEventListener("click", () => {
    if (state === "idle") startRecording();
    else if (state !== "stopping") stopRecording();
  });
  pauseButton.addEventListener("click", togglePause);
  cancelButton.addEventListener("click", cancelRecording);
  window.addEventListener("beforeunload", (event) => {
    if (starting || state !== "idle") event.preventDefault();
  });
  window.addEventListener("pagehide", resetLocalState);
  document.querySelectorAll("[data-locale]").forEach((button) => {
    button.addEventListener("click", () => localize());
  });

  localize();
  recoverOrphanSession();
}
