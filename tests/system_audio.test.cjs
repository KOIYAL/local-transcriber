// Run with node --test tests/system_audio.test.cjs. All media/OS/network APIs are fake.
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { systemAudioCapability, installSystemAudioHandler } = require("../desktop/system-audio");

test("desktop capability restricts macOS to packaged apps on 14.2+", () => {
  for (const [platform, version, packaged, supported] of [
    ["win32", "10.0", false, true], ["darwin", "14.2", true, true],
    ["darwin", "26.0", true, true], ["darwin", "14.1", true, false],
    ["darwin", "13.7", true, false], ["darwin", "26.0", false, false],
    ["darwin", "unknown", true, false], ["linux", "6.8", true, false],
  ]) {
    const result = systemAudioCapability(platform, version, packaged);
    assert.equal(result.supported, supported);
    assert.equal(Boolean(result.reason), !supported);
  }
});

test("desktop only grants local main-frame user requests; failures settle once", async () => {
  let handler;
  let calls = 0;
  let fail = false;
  let sources = [{ id: "screen:1" }];
  let afterSources = () => {};
  const contents = {
    mainFrame: { url: "http://127.0.0.1:8000/" }, isDestroyed: () => false,
    session: { setDisplayMediaRequestHandler: (fn) => { handler = fn; } },
  };
  const capability = { supported: true };
  installSystemAudioHandler(contents, {
    getSources: async (options) => {
      calls++;
      assert.deepEqual(options.types, ["screen"]);
      if (fail) throw new Error("denied");
      afterSources();
      return sources;
    },
  }, capability, () => "http://127.0.0.1:8000/");
  const request = {
    frame: contents.mainFrame, securityOrigin: "http://127.0.0.1:8000",
    userGesture: true, audioRequested: true, videoRequested: true,
  };
  const run = async (overrides = {}) => {
    const replies = [];
    await handler({ ...request, ...overrides }, (value) => replies.push(value));
    assert.equal(replies.length, 1);
    return replies[0];
  };
  assert.deepEqual(await run(), { video: sources[0], audio: "loopback" });
  assert.deepEqual(await run({ securityOrigin: "http://127.0.0.1:8000/" }),
    { video: sources[0], audio: "loopback" });
  for (const invalid of [
    { frame: null }, { frame: { url: contents.mainFrame.url } },
    { securityOrigin: "http://127.0.0.1:9000" }, { userGesture: false },
    { securityOrigin: "http://127.0.0.1:9000/" }, { securityOrigin: "invalid" },
    { audioRequested: false }, { videoRequested: false },
  ]) assert.deepEqual(await run(invalid), {});
  assert.equal(calls, 2);
  fail = true;
  assert.deepEqual(await run(), {});
  fail = false;
  sources = [];
  assert.deepEqual(await run(), {});
  sources = [{ id: "screen:1" }];
  afterSources = () => { contents.mainFrame.url = "https://example.org"; };
  assert.deepEqual(await run(), {});
  contents.mainFrame.url = request.securityOrigin;
  capability.supported = false;
  const before = calls;
  assert.deepEqual(await run(), {});
  assert.equal(calls, before);
});

test("sandboxed preload exposes capability without exposing capture APIs", () => {
  for (const policy of ["supported", "macos-version", "unsupported-os"]) {
    const exposed = {};
    vm.runInNewContext(fs.readFileSync("desktop/preload.js", "utf8"), {
      process: { argv: [`--lt-system-audio=${policy}`] },
      require: () => ({
        contextBridge: { exposeInMainWorld: (key, value) => { exposed[key] = value; } },
        ipcRenderer: { invoke() {} },
      }),
    });
    assert.equal(exposed.localTranscriber.systemAudio.supported, policy === "supported");
    assert.equal(typeof exposed.desktop.chooseExportDirectory, "function");
  }
});

test("preload settings bridge exposes only get/set with fixed IPC channels", () => {
  const exposed = {}, calls = [];
  vm.runInNewContext(fs.readFileSync("desktop/preload.js", "utf8"), {
    process: { argv: [] },
    require: () => ({
      contextBridge: { exposeInMainWorld: (key, value) => { exposed[key] = value; } },
      ipcRenderer: { sendSync(...args) { calls.push(args); return args[0] === 'settings:get' ? 'saved' : true; } },
    }),
  });
  const bridge = exposed.localTranscriber.settings;
  assert.deepEqual(Object.keys(bridge), ['get', 'set']);
  assert.equal(bridge.get('local-transcriber-glossary'), 'saved');
  assert.equal(bridge.set('lt.system-audio', 'true'), true);
  assert.deepEqual(calls, [
    ['settings:get', 'local-transcriber-glossary'], ['settings:set', 'lt.system-audio', 'true'],
  ]);
});

class Target {
  constructor() { this.listeners = {}; }
  addEventListener(name, fn) { (this.listeners[name] ||= []).push(fn); }
  emit(name, data = {}) { return Promise.all((this.listeners[name] || []).map((fn) => fn(data))); }
}
class Track extends Target {
  constructor(kind) { super(); this.kind = kind; this.readyState = "live"; }
  stop() { this.readyState = "ended"; }
  end() { this.stop(); return this.emit("ended"); }
}
class Stream {
  constructor(tracks) { this.tracks = tracks; }
  getTracks() { return this.tracks; }
  getAudioTracks() { return this.tracks.filter((track) => track.kind === "audio"); }
  getVideoTracks() { return this.tracks.filter((track) => track.kind === "video"); }
}
const settle = () => new Promise((resolve) => setImmediate(resolve));

test('preferences keep browser localStorage and tolerate unavailable storage', () => {
  const stored = new Map([['local-transcriber-glossary', 'KOIYAL']]);
  const window = { localStorage: {
    getItem: key => stored.get(key) ?? null,
    setItem: (key, value) => stored.set(key, value), removeItem: key => stored.delete(key),
  } };
  const load = () => vm.runInNewContext(fs.readFileSync('app/static/preferences.js', 'utf8'), { window });
  load();
  assert.equal(window.LTPreferences.get('local-transcriber-glossary'), 'KOIYAL');
  window.LTPreferences.set('lt.mic-device-id', 'mic');
  load();
  assert.equal(window.LTPreferences.get('lt.mic-device-id'), 'mic');
  window.LTPreferences.set('lt.mic-device-id', null);
  assert.equal(stored.has('lt.mic-device-id'), false);
  Object.defineProperty(window, 'localStorage', { get() { throw new Error('disabled'); } });
  load();
  assert.equal(window.LTPreferences.get('local-transcriber-glossary'), null);
  window.LTPreferences.set('local-transcriber-glossary', 'session');
  assert.equal(window.LTPreferences.get('local-transcriber-glossary'), 'session');
});

function recorderHarness(options = {}) {
  const elements = new Map();
  const element = (id) => {
    if (!elements.has(id)) elements.set(id, Object.assign(new Target(), {
      hidden: false, checked: false, disabled: false, style: {}, dataset: {},
      classList: { toggle() {} }, setAttribute() {}, replaceChildren() {},
      closest() { return this; },
    }));
    return elements.get(id);
  };
  const storage = new Map(options.saved ? [["lt.system-audio", "true"]] : []);
  const microphone = new Stream([new Track("audio")]);
  const display = new Stream([new Track("video"), ...(options.noAudio ? [] : [new Track("audio")])]);
  const mixed = new Stream([new Track("audio")]);
  const calls = [], toasts = [], recorders = [], contexts = [], nodes = [], requests = [];
  const timers = new Map();
  let locale = options.locale || "en";
  class AudioContext {
    constructor() { contexts.push(this); this.closed = false; }
    async resume() {}
    async close() { this.closed = true; }
    createMediaStreamDestination() { return { stream: mixed }; }
    createMediaStreamSource(stream) {
      if (options.mixError && stream === display) throw new Error("mix failed");
      const node = {
        stream, connections: [],
        connect(target) { this.connections.push(target); },
        disconnect() { this.connections = []; },
      };
      nodes.push(node);
      return node;
    }
    createAnalyser() { return { fftSize: 2048, getFloatTimeDomainData: (buffer) => buffer.fill(0.25) }; }
  }
  class MediaRecorder extends Target {
    static isTypeSupported() { return true; }
    constructor(stream) {
      super();
      if (options.recorderError) throw new Error("recorder failed");
      this.stream = stream; recorders.push(this);
    }
    start() { this.state = "recording"; }
    pause() { this.state = "paused"; }
    resume() { this.state = "recording"; }
    stop() {
      this.state = "inactive";
      this.emit("dataavailable", { data: { size: 5 } });
      this.emit("stop");
    }
  }
  const mediaDevices = {
    async enumerateDevices() { return []; },
    async getUserMedia(constraints) {
      calls.push(["mic", constraints]);
      if (options.micError) throw { name: "NotAllowedError" };
      if (options.missingMic && calls.filter(([type]) => type === "mic").length === 1) {
        throw { name: "OverconstrainedError" };
      }
      return microphone;
    },
    async getDisplayMedia(constraints) {
      calls.push(["display", constraints]);
      if (options.displayError) throw { name: options.displayError };
      if (options.pendingDisplay) await options.pendingDisplay;
      return display;
    },
  };
  if (options.noDisplayApi) delete mediaDevices.getDisplayMedia;
  const window = Object.assign(new Target(), {
    AudioContext, MediaRecorder,
    localStorage: { getItem: (key) => storage.get(key), setItem: (key, value) => storage.set(key, value), removeItem: (key) => storage.delete(key) },
    LT: { getLocale: () => locale, showToast: (text) => toasts.push(text), getGlossary: () => "Example", getDiarize: () => Boolean(options.diarize), trackJob: async () => {} },
    setInterval: (fn, ms) => { timers.set(ms, fn); return ms; },
    clearInterval: (id) => timers.delete(id), confirm: () => true,
  });
  if (options.desktop !== undefined) {
    window.desktop = {};
    window.localTranscriber = { systemAudio: { supported: options.desktop } };
  }
  if (options.preferences) window.localTranscriber = {
    ...window.localTranscriber,
    settings: { get: key => options.preferences.get(key) ?? null,
      set: (key, value) => value === null ? options.preferences.delete(key) : options.preferences.set(key, value) },
  };
  vm.runInNewContext(fs.readFileSync("app/static/preferences.js", "utf8"), { window });
  vm.runInNewContext(fs.readFileSync("app/static/recorder.js", "utf8"), {
    window, navigator: { mediaDevices }, AudioContext, MediaRecorder, FormData,
    document: {
      querySelector: element,
      querySelectorAll: (selector) => selector === "[data-locale]" ? [element("locale")] : [],
      createElement: () => ({}),
    },
    fetch: async (url, init = {}) => {
      requests.push([url, init]);
      if (options.deleteError && init.method === "DELETE") throw new Error("offline");
      if (options.pendingStop && url.endsWith("/stop")) await options.pendingStop;
      return {
        ok: !(options.startError && url.endsWith("/start")),
        json: async () => url.endsWith("/status") ? { state: "idle" } : { session_id: "session", id: "job" },
      };
    },
  });
  return {
    element, storage, microphone, display, mixed, calls, toasts, recorders, contexts, nodes, requests, timers, window,
    async click(id) { await element(id).emit("click"); await settle(); },
    async enable() { element("#system-audio-toggle").checked = true; await element("#system-audio-toggle").emit("change"); },
    async locale(value) { locale = value; await element("locale").emit("click"); },
  };
}

test("default remains microphone-only; unsupported environments hide saved opt-in", async () => {
  for (const options of [{}, { saved: true, desktop: false }, { saved: true, noDisplayApi: true }]) {
    const h = recorderHarness(options);
    assert.equal(h.element("#system-audio-toggle").checked, false);
    assert.equal(h.element("#system-audio-row").hidden, Boolean(options.saved));
    await h.click("#record-toggle");
    assert.equal(h.calls.length, 1);
    assert.equal(h.recorders[0].stream, h.microphone);
    await h.click("#record-toggle");
    assert.equal(h.microphone.getTracks()[0].readyState, "ended");
  }
});

test("recording stop forwards the optional speaker separation choice", async () => {
  for (const diarize of [false, true]) {
    const h = recorderHarness({ diarize });
    await h.click("#record-toggle");
    await h.click("#record-toggle");
    const request = h.requests.find(([url]) => url.endsWith("/stop"));
    assert.equal(request[1].body.get("diarize"), String(diarize));
  }
});

test("opt-in mixes audio only, meters the mix, pauses/resumes, uploads and releases all inputs", async () => {
  const h = recorderHarness({ desktop: true });
  await h.enable();
  assert.equal(h.storage.get("lt.system-audio"), "true");
  await h.click("#record-toggle");
  assert.deepEqual(h.calls.map(([type]) => type), ["display", "mic"]);
  assert.equal(h.display.getVideoTracks()[0].readyState, "ended");
  assert.equal(h.display.getAudioTracks()[0].readyState, "live");
  assert.equal(h.recorders[0].stream, h.mixed);
  assert.equal(h.nodes.filter((node) => node.connections[0]?.stream === h.mixed).length, 2);
  assert.equal(h.nodes.at(-1).stream, h.mixed);
  h.timers.get(200)();
  assert.equal(h.element("#level-bar").style.width, "75%");
  assert.equal(h.element("#system-audio-active").hidden, false);
  assert.equal(h.element("#system-audio-toggle").disabled, true);
  await h.click("#record-pause");
  assert.equal(h.recorders[0].state, "paused");
  await h.click("#record-pause");
  assert.equal(h.recorders[0].state, "recording");
  await h.click("#record-toggle");
  for (const stream of [h.microphone, h.display, h.mixed]) {
    assert.ok(stream.getTracks().every((track) => track.readyState === "ended"));
  }
  assert.ok(h.contexts[0].closed);
  assert.equal(h.timers.size, 0);
  const chunk = h.requests.find(([url]) => url.endsWith("/chunk"));
  assert.equal(chunk[1].headers["X-Audio-Level"], "0.2500");
  assert.equal(h.requests.find(([url]) => url.endsWith("/stop"))[1].body.get("glossary"), "Example");
  assert.equal(h.element("#system-audio-toggle").disabled, false);
});

for (const [name, options, message] of [
  ["denial", { displayError: "NotAllowedError" }, /canceled or denied/],
  ["capture failure", { displayError: "NotReadableError" }, /could not be captured/],
  ["no audio", { noAudio: true }, /no audio/],
  ["mix failure", { mixError: true }, /could not be captured or mixed/],
]) test(`${name} turns off saved opt-in and continues microphone recording`, async () => {
  const h = recorderHarness({ ...options, saved: true });
  await h.click("#record-toggle");
  assert.equal(h.recorders[0].stream, h.microphone);
  assert.equal(h.element("#system-audio-toggle").checked, false);
  assert.equal(h.storage.get("lt.system-audio"), "false");
  assert.match(h.toasts[0], message);
  if (!options.displayError) assert.ok(h.display.getTracks().every((track) => track.readyState === "ended"));
  await h.click("#record-cancel");
});

test("sharing ending mid-recording disconnects only computer audio and localizes notice", async () => {
  const h = recorderHarness({ saved: true });
  await h.click("#record-toggle");
  await h.locale("ja");
  await h.display.getAudioTracks()[0].end();
  assert.match(h.toasts[0], /PC 音声の共有が終了/);
  assert.equal(h.microphone.getAudioTracks()[0].readyState, "live");
  assert.equal(h.recorders[0].state, "recording");
  assert.equal(h.nodes.find((node) => node.stream === h.display).connections.length, 0);
  assert.equal(h.element("#system-audio-active").hidden, true);
  await h.click("#record-toggle");
});

for (const options of [{ micError: true }, { startError: true }, { recorderError: true }]) {
  test(`start failure releases capture: ${Object.keys(options)[0]}`, async () => {
    const h = recorderHarness({ ...options, saved: true });
    await h.click("#record-toggle");
    assert.ok(h.display.getTracks().every((track) => track.readyState === "ended"));
    assert.equal(h.element("#record-toggle").disabled, false);
    assert.equal(h.element("#system-audio-toggle").disabled, false);
    if (!options.micError) assert.equal(h.microphone.getTracks()[0].readyState, "ended");
    if (options.recorderError) {
      assert.ok(h.contexts[0].closed);
      assert.ok(h.requests.some(([, init]) => init.method === "DELETE"));
    }
  });
}

test("discard releases all inputs even if backend deletion fails", async () => {
  const h = recorderHarness({ saved: true, deleteError: true });
  await h.click("#record-toggle");
  await h.click("#record-cancel");
  assert.equal(h.microphone.getTracks()[0].readyState, "ended");
  assert.ok(h.display.getTracks().every((track) => track.readyState === "ended"));
  assert.ok(h.contexts[0].closed);
  assert.equal(h.element("#record-toggle").disabled, false);
});

test("capture is released before waiting for the backend to finish saving", async () => {
  let resolve;
  const pendingStop = new Promise((done) => { resolve = done; });
  const h = recorderHarness({ saved: true, pendingStop });
  await h.click("#record-toggle");
  await h.click("#record-toggle");
  assert.ok(h.display.getTracks().every((track) => track.readyState === "ended"));
  assert.equal(h.microphone.getTracks()[0].readyState, "ended");
  assert.ok(h.contexts[0].closed);
  assert.equal(h.element("#record-toggle").disabled, true);
  resolve();
  await settle();
  assert.equal(h.element("#record-toggle").disabled, false);
});

test("desktop microphone and PC audio choices restore, persist and clear on capture failure", async () => {
  const preferences = new Map([['lt.mic-device-id', 'saved-mic'], ['lt.system-audio', 'true']]);
  const h = recorderHarness({ desktop: true, preferences });
  assert.equal(h.element('#system-audio-toggle').checked, true);
  await h.click('#record-toggle');
  assert.equal(h.calls.find(([type]) => type === 'mic')[1].audio.deviceId.exact, 'saved-mic');
  await h.window.emit('pagehide');
  h.element('#mic-select').value = 'other-mic';
  await h.element('#mic-select').emit('change');
  h.element('#system-audio-toggle').checked = false;
  await h.element('#system-audio-toggle').emit('change');
  assert.equal(preferences.get('lt.mic-device-id'), 'other-mic');
  assert.equal(preferences.get('lt.system-audio'), 'false');
  assert.equal(h.storage.size, 0);

  const next = recorderHarness({ desktop: true, preferences, missingMic: true, displayError: 'NotAllowedError' });
  assert.equal(next.element('#system-audio-toggle').checked, false);
  await next.enable();
  await next.click('#record-toggle');
  assert.equal(preferences.has('lt.mic-device-id'), false);
  assert.equal(preferences.get('lt.system-audio'), 'false');
  assert.equal(next.calls.find(([type]) => type === 'mic')[1].audio.deviceId.exact, 'other-mic');
  assert.equal(next.calls.filter(([type]) => type === 'mic')[1][1].audio, true);
  assert.equal(next.storage.size, 0);
  await next.window.emit('pagehide');
});

test("pending picker blocks duplicate starts; missing saved mic falls back; page exit releases inputs", async () => {
  let resolve;
  const pendingDisplay = new Promise((done) => { resolve = done; });
  const h = recorderHarness({ saved: true, pendingDisplay, missingMic: true });
  await h.click("#record-toggle");
  await h.click("#record-toggle");
  assert.equal(h.calls.length, 1);
  assert.equal(h.element("#system-audio-toggle").disabled, true);
  resolve();
  await settle();
  assert.equal(h.recorders.length, 1);
  assert.equal(h.calls.filter(([type]) => type === "mic").length, 2);
  await h.window.emit("pagehide");
  assert.ok(h.display.getTracks().every((track) => track.readyState === "ended"));
  assert.equal(h.microphone.getTracks()[0].readyState, "ended");
});
