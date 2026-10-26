// Electron and backend APIs are fake: no display, processes or network needed.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

function harness(platform = 'linux', trayFailure = null, disk = new Map()) {
  const calls = { hidden: 0, quit: 0, warnings: 0, killed: 0, destroyed: 0 };
  const timers = new Map();
  const handlers = new Map();
  const invokeHandlers = new Map();
  calls.logActions = [];
  let choice = 0, recordingState = 'idle', window;
  const app = new EventEmitter();
  Object.assign(app, {
    isPackaged: true,
    requestSingleInstanceLock: () => true,
    whenReady: () => ({ then() {} }),
    getLocale: () => 'en',
    getPath: () => '/fake/userData',
    getLoginItemSettings: () => ({ openAtLogin: false }),
    quit() {
      const event = closeEvent();
      app.emit('before-quit', event);
      if (!event.prevented) calls.quit++;
    },
  });
  class Window extends EventEmitter {
    constructor() {
      super();
      window = this;
      this.webContents = new EventEmitter();
      this.webContents.mainFrame = { url: 'http://127.0.0.1:1234/' };
      this.webContents.setWindowOpenHandler = () => {};
    }
    hide() { calls.hidden++; }
  }
  class Tray extends EventEmitter {
    constructor() {
      super();
      if (trayFailure === 'constructor') throw new Error('No tray');
    }
    setToolTip() {}
    setImage() {}
    setContextMenu(menu) {
      if (trayFailure === 'menu') throw new Error('No menu host');
      calls.menu = menu;
    }
    destroy() { calls.destroyed++; }
  }
  const electron = {
    app, BrowserWindow: Window, Tray,
    Menu: { buildFromTemplate: items => items },
    nativeImage: { createFromPath: value => value },
    ipcMain: { handle(channel, handler) { invokeHandlers.set(channel, handler); },
      on(channel, handler) { handlers.set(channel, handler); } },
    shell: { async openPath(directory) {
      calls.logActions.push(['open', directory]);
      return calls.openError || '';
    } },
    dialog: { showMessageBoxSync() { calls.warnings++; return choice; } },
  };
  const context = vm.createContext({
    __dirname: path.resolve('desktop'), URL,
    process: { platform, getSystemVersion: () => '10.0', env: {}, resourcesPath: '/fake/resources' },
    require(name) {
      if (name === 'electron') return electron;
      if (name === './system-audio') return {
        systemAudioCapability: () => ({ supported: false, reason: 'unsupportedOS' }),
        installSystemAudioHandler() {},
      };
      if (name === 'node:child_process' || name === 'node:net') return {};
      if (name === 'node:fs') return {
        readFileSync(file) { if (!disk.has(file)) throw new Error('missing'); return disk.get(file); },
        writeFileSync(file, value) { disk.set(file, value); },
        mkdirSync(directory, options) {
          calls.logActions.push(['mkdir', directory, options.recursive]);
          if (calls.mkdirError) throw new Error('unavailable');
        },
      };
      return require(name);
    },
    fetch: async url => ({ ok: true, json: async () =>
      url.endsWith('/api/recording/status') ? { state: recordingState }
        : url.endsWith('/api/jobs') ? { jobs: [] } : { checked: false } }),
    setInterval(fn) { const id = Symbol(); timers.set(id, fn); return id; },
    clearInterval(id) { timers.delete(id); },
    fakeBackend: { exitCode: null, kill() { calls.killed++; } },
  });
  vm.runInContext(fs.readFileSync('desktop/main.js', 'utf8'), context);
  const run = code => vm.runInContext(code, context);
  run('loadSettings(); backendUrl = "http://127.0.0.1:1234"; backendProcess = fakeBackend; createWindow()');
  return { calls, timers, run, app,
    invoke(channel, overrides = {}, ...args) {
      return invokeHandlers.get(channel)({ sender: window.webContents,
        senderFrame: window.webContents.mainFrame, ...overrides }, ...args);
    },
    ipc(channel, args, overrides = {}) {
      const event = { sender: window.webContents, senderFrame: window.webContents.mainFrame, ...overrides };
      let replies = 0, reply;
      Object.defineProperty(event, 'returnValue', { set(value) {
        replies++;
        reply = value;
        if (channel === 'settings:set' && value === true) {
          const saved = JSON.parse(disk.get('/fake/userData/settings.json'));
          assert.equal(saved[args[0]] ?? null, args[1]);
        }
      } });
      handlers.get(channel)(event, ...args);
      assert.equal(replies, 1);
      return reply;
    },
    port(port) {
      run(`backendUrl = "http://127.0.0.1:${port}"`);
      window.webContents.mainFrame.url = `http://127.0.0.1:${port}/`;
    },
    close() { const event = closeEvent(); window.emit('close', event); return event; },
    choose(value) { choice = value; },
    async poll(state) { recordingState = state; await run('pollBackendState()'); },
  };
}

function closeEvent() {
  return { prevented: false, preventDefault() { this.prevented = true; } };
}

test('Linux close quits with or without a tray and stops the backend', () => {
  for (const failure of [null, 'constructor', 'menu']) {
    const h = harness('linux', failure);
    h.run('createTray()');
    assert.equal(h.timers.size, 1);
    assert.equal(h.close().prevented, true);
    assert.equal(h.calls.quit, 1);
    assert.equal(h.calls.hidden, 0);
    assert.equal(h.calls.killed, 1);
    assert.equal(h.timers.size, 0);
    assert.equal(h.calls.destroyed, failure === 'constructor' ? 0 : 1);
    assert.equal(h.close().prevented, false);
  }
});

test('Linux recording and pause guard work even after tray creation fails', async () => {
  for (const failure of [null, 'constructor', 'menu']) {
    for (const state of ['recording', 'paused']) {
      const h = harness('linux', failure);
      h.run('createTray()');
      await h.poll(state);
      h.close();
      assert.equal(h.calls.warnings, 1);
      assert.equal(h.calls.quit, 0);
      assert.equal(h.calls.killed, 0);
      assert.equal(h.calls.hidden, 0);
      assert.equal(h.timers.size, 1);
      h.choose(1);
      h.close();
      assert.equal(h.calls.quit, 1);
      assert.equal(h.calls.killed, 1);
      assert.equal(h.timers.size, 0);
    }
  }
});

test('stopping a recording clears the quit warning without a tray', async () => {
  const h = harness('linux', 'constructor');
  h.run('createTray()');
  await h.poll('recording');
  await h.poll('idle');
  h.close();
  assert.equal(h.calls.warnings, 0);
  assert.equal(h.calls.quit, 1);
});

test('Windows and macOS still hide on close and guard quitting during recording', async () => {
  for (const platform of ['win32', 'darwin']) {
    const h = harness(platform);
    h.run('createTray()');
    await h.poll('recording');
    assert.equal(h.close().prevented, true);
    assert.equal(h.calls.hidden, 1);
    assert.equal(h.calls.quit, 0);
    h.app.quit();
    assert.equal(h.calls.warnings, 1);
    assert.equal(h.calls.killed, 0);
    h.choose(1);
    h.app.quit();
    assert.equal(h.calls.quit, 1);
    assert.equal(h.calls.killed, 1);
  }
});

test('Linux tray omits unsupported login and OS sound settings controls', () => {
  const h = harness();
  h.run('createTray()');
  const labels = h.calls.menu.map(item => item.label);
  assert.ok(labels.includes('Start recording'));
  assert.ok(labels.includes('Quit'));
  assert.ok(!labels.includes('Start at login'));
  assert.ok(!labels.includes('Open system sound settings'));
});

test('packaged Linux starts the bundled backend with its executable path', () => {
  const h = harness();
  const command = h.run('backendCommand(4321)');
  assert.equal(command.executable, '/fake/resources/local-transcriber-backend/local-transcriber-backend');
  assert.equal(command.cwd, '/fake/resources/local-transcriber-backend');
  assert.deepEqual(Array.from(command.args), ['--port', '4321']);
});

test('preferences survive a new desktop process and backend port in settings.json', () => {
  const disk = new Map();
  const h = harness('linux', null, disk);
  const values = {
    'local-transcriber-glossary': 'KOIYAL、人名', 'local-transcriber-locale': 'ja',
    'lt.mic-device-id': 'microphone-2', 'lt.system-audio': 'true',
  };
  for (const [key, value] of Object.entries(values)) {
    assert.equal(h.ipc('settings:get', [key]), null);
    assert.equal(h.ipc('settings:set', [key, value]), true);
    assert.equal(h.ipc('settings:get', [key]), value);
  }
  const next = harness('linux', null, disk);
  next.port(4321);
  for (const [key, value] of Object.entries(values)) assert.equal(next.ipc('settings:get', [key]), value);
  assert.equal(next.ipc('settings:set', ['lt.mic-device-id', null]), true);
  assert.equal(harness('linux', null, disk).ipc('settings:get', ['lt.mic-device-id']), null);
  assert.equal(JSON.parse(disk.get('/fake/userData/settings.json')).exportDirectory, null);
});

test('settings IPC rejects unrelated frames, keys and invalid values', () => {
  const h = harness();
  const key = 'local-transcriber-glossary';
  for (const overrides of [
    { sender: {} }, { senderFrame: null },
    { senderFrame: { url: 'http://127.0.0.1:1234/' } },
  ]) {
    assert.equal(h.ipc('settings:set', [key, 'blocked'], overrides), false);
    assert.equal(h.ipc('settings:get', [key], overrides), null);
  }
  h.run('mainWindow.webContents.mainFrame.url = "https://example.invalid/"');
  assert.equal(h.ipc('settings:set', [key, 'blocked']), false);
  h.port(1234);
  for (const [key, value] of [
    ['exportDirectory', '/tmp'], ['__proto__', 'bad'], ['unknown', 'bad'],
    ['local-transcriber-glossary', 'x'.repeat(501)], ['local-transcriber-glossary', {}],
    ['local-transcriber-locale', 'xx'], ['lt.system-audio', true], ['lt.system-audio', 'yes'],
  ]) assert.equal(h.ipc('settings:set', [key, value]), false);
  assert.equal(h.ipc('settings:get', ['exportDirectory']), null);
  assert.equal(h.ipc('settings:get', [key]), null);
});

for (const platform of ['linux', 'win32', 'darwin']) {
  test(`logs IPC creates and opens only the configured logs folder on ${platform}`, async () => {
    const h = harness(platform);
    assert.equal(await h.invoke('logs:open'), false); // Backend not initialized.
    assert.equal(h.calls.logActions.length, 0);
    h.run('dataDirectory = "/fake/userData/日本語/data"');
    assert.equal(await h.invoke('logs:open', {}, '/untrusted/path'), true);
    assert.deepEqual(h.calls.logActions, [
      ['mkdir', '/fake/userData/日本語/data/logs', true],
      ['open', '/fake/userData/日本語/data/logs'],
    ]);
    for (const overrides of [{ sender: {} }, { senderFrame: null },
      { senderFrame: { url: 'http://127.0.0.1:1234/' } }]) {
      assert.equal(await h.invoke('logs:open', overrides), false);
    }
    h.run('mainWindow.webContents.mainFrame.url = "https://example.invalid/"');
    assert.equal(await h.invoke('logs:open'), false);
    assert.equal(h.calls.logActions.length, 2);
  });
}

test('logs IPC reports directory and OS open failures without throwing', async () => {
  const h = harness();
  h.run('dataDirectory = "/fake/userData/data"');
  h.calls.mkdirError = true;
  assert.equal(await h.invoke('logs:open'), false);
  assert.equal(h.calls.logActions.length, 1);
  h.calls.mkdirError = false;
  h.calls.openError = 'No application available';
  assert.equal(await h.invoke('logs:open'), false);
});

test('preload exposes a fixed logs IPC call with no caller-supplied path', async () => {
  const exposed = {}, calls = [];
  vm.runInNewContext(fs.readFileSync('desktop/preload.js', 'utf8'), {
    process: { argv: [] },
    require: () => ({
      contextBridge: { exposeInMainWorld(key, value) { exposed[key] = value; } },
      ipcRenderer: { invoke(...args) { calls.push(args); return Promise.resolve(true); } },
    }),
  });
  assert.equal(await exposed.desktop.openLogsFolder('/ignored'), true);
  assert.deepEqual(calls, [['logs:open']]);
});
