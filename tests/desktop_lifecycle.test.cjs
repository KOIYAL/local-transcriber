// Electron and backend APIs are fake: no display, processes or network needed.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { EventEmitter } = require('node:events');

function harness(platform = 'linux', trayFailure = null) {
  const calls = { hidden: 0, quit: 0, warnings: 0, killed: 0, destroyed: 0 };
  const timers = new Map();
  let choice = 0, recordingState = 'idle', window;
  const app = new EventEmitter();
  Object.assign(app, {
    isPackaged: true,
    requestSingleInstanceLock: () => true,
    whenReady: () => ({ then() {} }),
    getLocale: () => 'en',
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
    ipcMain: { handle() {} },
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
  run('backendUrl = "http://127.0.0.1:1234"; backendProcess = fakeBackend; createWindow()');
  return { calls, timers, run, app,
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
