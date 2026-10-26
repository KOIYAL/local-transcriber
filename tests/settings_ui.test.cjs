const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const settle = () => new Promise(resolve => setImmediate(resolve));
const latest = { checked: true, current: '0.7.2', latest: '0.7.3', update_available: true,
  url: 'https://github.com/KOIYAL/local-transcriber/releases/tag/v0.7.3' };

function harness({ locale = 'ja', appCheck = { ...latest, update_available: false },
  modelCheck = { current: 'small', recommended: 'turbo', upgrade_available: false },
  answers = [], appError = null, modelError = false, upgradeError = false, desktop = null } = {}) {
  const elements = new Map(), calls = [], prompts = [], opened = [], notices = [];
  let reloads = 0;
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', checked: false, disabled: false, hidden: false, style: {}, dataset: {},
      listeners: {}, children: [], textContent: '', classList: { add() {}, remove() {} },
      addEventListener(event, fn) { this.listeners[event] = fn; },
      querySelector() { return this; },
      setAttribute() {}, removeAttribute(key) { delete this[key]; },
      replaceChildren() {}, append() {}, scrollIntoView() {},
    });
    return elements.get(id);
  }
  for (const [id, key] of [['#model-check', 'modelCheck'], ['#logs-open', 'logsOpen']]) {
    element(id).dataset.settingsI18n = key;
  }
  const localeButton = element('#locale-button');
  const window = {
    desktop, localStorage: { getItem() { return null; }, setItem() {} },
    setTimeout() { return 1; }, clearTimeout() {},
    confirm(message) { prompts.push(message); return answers.shift() ?? false; },
    open(...args) { opened.push(args); }, location: { reload() { reloads++; } },
  };
  const context = vm.createContext({
    window, navigator: { language: locale },
    document: { querySelector: element, documentElement: {},
      querySelectorAll(selector) {
        if (selector === '[data-settings-i18n]') return [...elements.values()].filter(e => e.dataset.settingsI18n);
        if (selector === '[data-locale]') return [localeButton];
        return [];
      }, createElement: () => element('#created') },
    fetch: async (url, init = {}) => {
      calls.push([url, init]);
      if (url === '/api/update-check?force=true' && appError === 'network') throw new Error('offline');
      const data = url === '/api/config' ? { max_upload_mb: 10 }
        : url === '/api/setup' ? { ready: true, model: 'small' }
        : url === '/api/update-check' ? { checked: false }
        : url === '/api/update-check?force=true' ? appCheck
        : url === '/api/models/upgrade-check' ? modelCheck : {};
      const failed = (url === '/api/update-check?force=true' && appError === 'http')
        || (url === '/api/models/upgrade-check' && modelError)
        || (url === '/api/models/upgrade' && upgradeError);
      return { ok: !failed, json: async () => data };
    },
  });
  for (const file of ['preferences.js', 'app.js', 'settings.js']) {
    vm.runInContext(fs.readFileSync(`app/static/${file}`, 'utf8'), context);
  }
  window.LT.showToast = message => notices.push(message);
  return { window, element, calls, prompts, opened, notices,
    reloads: () => reloads,
    click: () => element('#model-check').listeners.click(),
    locale(value) { vm.runInContext(`applyLanguage(${JSON.stringify(value)}, false)`, context); localeButton.listeners.click(); },
  };
}

test('update button is localized and confirms both current with the app version', async () => {
  const h = harness(); await settle();
  assert.equal(h.element('#model-check').textContent, 'アップデートを確認');
  await h.click();
  assert.deepEqual(h.notices, ['アプリもモデルも最新です（0.7.2）']);
  assert.equal(h.element('#model-check').disabled, false);
  h.locale('en'); await settle();
  assert.equal(h.element('#model-check').textContent, 'Check for updates');
  await h.click();
  assert.equal(h.notices.at(-1), 'The app and model are up to date (0.7.2).');
  assert.equal(h.prompts.length, 0);
});

for (const acceptApp of [false, true]) {
  test(`new app notice and external download (${acceptApp}) precede normal model upgrade`, async () => {
    const h = harness({ appCheck: latest, answers: [acceptApp, true],
      modelCheck: { current: 'small', recommended: 'turbo', upgrade_available: true } });
    await settle();
    const start = h.calls.length;
    const checking = h.click();
    assert.equal(h.element('#model-check').disabled, true);
    await h.click(); // A repeated click cannot start a second check.
    await checking;
    assert.equal(h.element('#update-notice').hidden, false);
    assert.equal(h.element('#update-link').href, latest.url);
    assert.match(h.prompts[0], /新しいバージョン 0.7.3.*ダウンロードページ/);
    assert.match(h.prompts[1], /small.*turbo/);
    assert.deepEqual(h.opened, acceptApp ? [[latest.url, '_blank', 'noopener,noreferrer']] : []);
    assert.deepEqual(h.calls.slice(start).map(([url]) => url), [
      '/api/update-check?force=true', '/api/models/upgrade-check', '/api/models/upgrade',
    ]);
    assert.equal(h.calls.at(-1)[1].method, 'POST');
    assert.equal(h.reloads(), 1);
    assert.equal(h.element('#model-check').disabled, false);
  });
}

for (const failure of ['disabled', 'network', 'http']) {
  test(`unavailable app check (${failure}) still offers the model upgrade`, async () => {
    const h = harness({ appCheck: { checked: false }, appError: failure,
      modelCheck: { current: 'small', recommended: 'turbo', upgrade_available: true }, answers: [true] });
    await settle(); await h.click();
    assert.match(h.notices[0], /停止中.*オフライン/);
    assert.equal(h.prompts.length, 1);
    assert.equal(h.reloads(), 1);
    assert.equal(h.element('#model-check').disabled, false);
  });
}

test('declining a model upgrade does not download or reload', async () => {
  const h = harness({ modelCheck: { current: 'small', recommended: 'turbo', upgrade_available: true }, answers: [false] });
  await settle(); await h.click();
  assert.equal(h.reloads(), 0);
  assert.equal(h.calls.some(([url]) => url === '/api/models/upgrade'), false);
});

test('unsafe release URLs cannot open or appear in the update notice', async () => {
  const h = harness({ appCheck: { ...latest, url: 'https://evil.invalid/download' }, answers: [true] });
  await settle(); await h.click();
  assert.equal(h.element('#update-notice').hidden, true);
  assert.equal(h.element('#update-link').href, undefined);
  assert.equal(h.prompts.length, 0);
  assert.equal(h.opened.length, 0);
});

for (const failure of ['modelError', 'upgradeError']) {
  test(`${failure} is localized and re-enables the button`, async () => {
    const h = harness({ locale: 'en', [failure]: true, answers: [true],
      modelCheck: { current: 'small', recommended: 'turbo', upgrade_available: true } });
    await settle(); await h.click();
    assert.equal(h.notices.at(-1), 'The model check failed.');
    assert.equal(h.element('#model-check').disabled, false);
    assert.equal(h.reloads(), 0);
  });
}

test('logs row is hidden in browsers and localized in the desktop app', async () => {
  const browser = harness(); await settle();
  assert.equal(browser.element('#logs-row').hidden, true);
  assert.equal(browser.element('#logs-open').listeners.click, undefined);
  let calls = 0;
  const desktop = harness({ desktop: {
    getExportDirectory: async () => null,
    openLogsFolder: async () => { calls++; return true; },
  } });
  await settle();
  assert.equal(desktop.element('#logs-row').hidden, false);
  assert.equal(desktop.element('#logs-open').textContent, 'ログフォルダを開く');
  await desktop.element('#logs-open').listeners.click();
  assert.equal(calls, 1);
  assert.equal(desktop.element('#logs-open').disabled, false);
  desktop.locale('en');
  assert.equal(desktop.element('#logs-open').textContent, 'Open logs folder');
});

for (const throws of [false, true]) {
  test(`logs open failure (${throws ? 'rejected IPC' : 'OS error'}) shows a localized message`, async () => {
    const h = harness({ desktop: {
      getExportDirectory: async () => null,
      openLogsFolder: async () => { if (throws) throw new Error('IPC'); return false; },
    } });
    await settle();
    await h.element('#logs-open').listeners.click();
    assert.equal(h.notices.at(-1), 'ログフォルダを開けませんでした。');
    assert.equal(h.element('#logs-open').disabled, false);
    h.locale('en');
    await h.element('#logs-open').listeners.click();
    assert.equal(h.notices.at(-1), 'Could not open the logs folder.');
  });
}
