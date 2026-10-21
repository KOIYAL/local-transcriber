// Run with node --test tests/diarization_ui.test.cjs; all browser/network APIs are fake.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const settle = () => new Promise(resolve => setImmediate(resolve));

function harness(initial = { available: true, ready: false, status: 'not_started' }) {
  const elements = new Map(), calls = [], timers = new Map();
  function element(id) {
    if (!elements.has(id)) elements.set(id, {
      value: '', checked: false, disabled: false, hidden: false, style: {}, dataset: {},
      listeners: {}, children: [], classList: { add() {}, remove() {} },
      addEventListener(name, fn) { this.listeners[name] = fn; },
      querySelector() { return this; }, setAttribute() {}, removeAttribute() {},
      replaceChildren(...children) { this.children = children; },
      append(...children) { this.children.push(...children); }, scrollIntoView() {},
    });
    return elements.get(id);
  }
  const window = { setTimeout(fn) { const id = Symbol(); timers.set(id, fn); return id; },
    clearTimeout(id) { timers.delete(id); } };
  let next = initial, fail = false, created = 0;
  const context = vm.createContext({
    window, navigator: { language: 'ja' },
    localStorage: { getItem() { return null; }, setItem() {} },
    document: { querySelector: element, querySelectorAll: () => [], documentElement: {},
      createElement: () => element(`created-${created++}`) },
    FormData: class { constructor() { this.data = new Map(); } set(k,v) { this.data.set(k,v); } get(k) { return this.data.get(k); } },
    fetch: async (url, init = {}) => {
      calls.push([url, init]);
      if (url === '/api/diarize/setup' && fail) throw new Error('offline');
      const data = url === '/api/config' ? { max_upload_mb: 10, diarize: initial }
        : url === '/api/diarize/setup' ? next
        : url === '/api/setup' ? { ready: true }
        : url === '/api/update-check' ? { checked: false }
        : url === '/api/jobs' ? { id: 'job', status: 'queued' }
        : { id: 'job', status: 'failed', error: 'fake stop polling' };
      return { ok: true, json: async () => data };
    },
  });
  vm.runInContext(fs.readFileSync('app/static/app.js', 'utf8'), context);
  return { element, calls, timers, window,
    run(code) { return vm.runInContext(code, context); },
    respond(value) { next = value; }, fail() { fail = true; },
    async change() { await element('#diarize').listeners.change(); await settle(); },
    async tick() { const [id, fn] = timers.entries().next().value; timers.delete(id); await fn(); await settle(); },
  };
}

test('hidden when unavailable; no model requests on load, even with ready models', async () => {
  for (const available of [false, true]) {
    const h = harness({ available, ready: available, status: available ? 'ready' : 'unavailable' });
    await settle();
    assert.equal(h.element('#diarize-panel').hidden, !available);
    assert.equal(h.window.LT.getDiarize(), false);
    assert.equal(h.calls.some(([url]) => url === '/api/diarize/setup'), false);
  }
});

test('explicit setup polls progress, enables only after ready and supports switching off', async () => {
  const h = harness(); await settle();
  h.respond({ available: true, ready: false, status: 'downloading', progress: .4 });
  h.element('#diarize').checked = true;
  await h.change();
  assert.equal(h.calls.at(-1)[1].method, 'POST');
  assert.equal(h.window.LT.getDiarize(), false);
  assert.equal(h.element('#diarize').disabled, true);
  assert.equal(h.element('#diarize-progress').value, .4);
  assert.match(h.element('#diarize-message').textContent, /40%/);
  h.run('applyLanguage("en", false)');
  assert.match(h.element('#diarize-message').textContent, /Preparing speaker models/);
  h.respond({ available: true, ready: true, status: 'ready', progress: 1 });
  await h.tick();
  assert.equal(h.calls.at(-1)[1].method, 'GET');
  assert.equal(h.window.LT.getDiarize(), true);
  h.element('#diarize').checked = false;
  await h.change();
  assert.equal(h.window.LT.getDiarize(), false);
});

test('setup failure and fetch failure allow normal transcription with a retry', async () => {
  for (const network of [false, true]) {
    const h = harness(); await settle();
    if (network) h.fail();
    else h.respond({ available: true, ready: false, status: 'failed' });
    h.element('#diarize').checked = true;
    await h.change();
    assert.equal(h.window.LT.getDiarize(), false);
    assert.equal(h.element('#diarize').disabled, false);
    assert.equal(h.element('#diarize-retry').hidden, false);
    assert.match(h.element('#diarize-message').textContent, /準備できません/);
  }
});

test('file upload sends selected diarization and results render labels as text', async () => {
  const h = harness({ available: true, ready: true, status: 'ready' }); await settle();
  h.element('#diarize').checked = true;
  h.run('setFile({ name: "sample.wav", size: 4 })');
  await h.element('#transcription-form').listeners.submit({ preventDefault() {} });
  const request = h.calls.find(([url]) => url === '/api/jobs');
  assert.equal(request[1].body.get('diarize'), 'true');
  h.run('renderResult({ status: "completed", filename: "sample.wav", result: { duration: 2, language: "ja", segments: [{ start: 0, end: 1, speaker: "話者1", text: "<script>" }] } })');
  assert.equal(h.element('#transcript').children[0].children[1].textContent, '話者1: <script>');
  h.run('updateProgress({ status: "diarizing", progress: .91 })');
  assert.equal(h.element('#progress-title').textContent, '話者を分けています');
  h.run('updateResultMeta({ filename: "a", result: { duration: 2, language: "ja", diarization_failed: true } })');
  assert.match(h.element('#result-meta').textContent, /元音声を残しました/);
});
