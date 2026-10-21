// Keep OS policy and capture authorization testable without launching Electron.
function systemAudioCapability(platform, systemVersion, isPackaged) {
  if (platform === "win32") return { supported: true, reason: "" };
  if (platform === "darwin") {
    const [major, minor] = systemVersion.split(".").map(Number);
    if (!(major > 14 || (major === 14 && minor >= 2))) {
      return { supported: false, reason: "macos-version" };
    }
    // A terminal/IDE launch may lack the required audio capture usage key.
    if (!isPackaged) return { supported: false, reason: "macos-packaged-only" };
    return { supported: true, reason: "" };
  }
  return { supported: false, reason: "unsupported-os" };
}

function installSystemAudioHandler(webContents, desktopCapturer, capability, getBackendUrl) {
  webContents.session.setDisplayMediaRequestHandler(async (request, callback) => {
    const allowed = () => {
      try {
        const origin = new URL(request.securityOrigin).origin;
        return capability.supported && !webContents.isDestroyed()
          && request.frame === webContents.mainFrame
          && request.userGesture && request.audioRequested && request.videoRequested
          && origin === new URL(getBackendUrl()).origin
          && new URL(request.frame.url).origin === origin;
      } catch {
        return false;
      }
    };
    let streams = {};
    if (allowed()) {
      try {
        const sources = await desktopCapturer.getSources({
          types: ["screen"], thumbnailSize: { width: 0, height: 0 },
        });
        if (sources[0] && allowed()) streams = { video: sources[0], audio: "loopback" };
      } catch {
        // Denial/no display reaches the renderer's microphone-only fallback.
      }
    }
    callback(streams);
  });
}

module.exports = { systemAudioCapability, installSystemAudioHandler };
