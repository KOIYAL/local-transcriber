import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";


const [, , debugPort, locale, outputDirectory] = process.argv;
if (!debugPort || !["ja", "en"].includes(locale) || !outputDirectory) {
  console.error(
    "Usage: node capture_store_screenshots.mjs <debug-port> <ja|en> <output-dir>",
  );
  process.exit(2);
}

const pageUrl = "http://127.0.0.1:8765";
const target = await fetch(
  `http://127.0.0.1:${debugPort}/json/new?${encodeURIComponent(pageUrl)}`,
  { method: "PUT" },
).then((response) => {
  if (!response.ok) {
    throw new Error(`Could not create Chrome target: ${response.status}`);
  }
  return response.json();
});

const socket = new WebSocket(target.webSocketDebuggerUrl);
const pending = new Map();
const eventWaiters = new Map();
let commandId = 0;

socket.addEventListener("message", (event) => {
  const message = JSON.parse(event.data);
  if (message.id) {
    const request = pending.get(message.id);
    if (!request) return;
    pending.delete(message.id);
    if (message.error) request.reject(new Error(message.error.message));
    else request.resolve(message.result);
    return;
  }

  const waiters = eventWaiters.get(message.method) || [];
  eventWaiters.delete(message.method);
  for (const resolve of waiters) resolve(message.params);
});

await new Promise((resolve, reject) => {
  socket.addEventListener("open", resolve, { once: true });
  socket.addEventListener("error", reject, { once: true });
});

function send(method, params = {}) {
  commandId += 1;
  return new Promise((resolve, reject) => {
    pending.set(commandId, { resolve, reject });
    socket.send(JSON.stringify({ id: commandId, method, params }));
  });
}

function waitForEvent(method) {
  return new Promise((resolve) => {
    const waiters = eventWaiters.get(method) || [];
    waiters.push(resolve);
    eventWaiters.set(method, waiters);
  });
}

const sleep = (milliseconds) =>
  new Promise((resolve) => setTimeout(resolve, milliseconds));

async function evaluate(expression) {
  const response = await send("Runtime.evaluate", {
    expression,
    awaitPromise: true,
    returnByValue: true,
  });
  if (response.exceptionDetails) {
    const description =
      response.exceptionDetails.exception?.description ||
      response.exceptionDetails.text;
    throw new Error(description);
  }
  return response.result.value;
}

async function capture(filename) {
  await sleep(250);
  const screenshot = await send("Page.captureScreenshot", {
    format: "png",
    captureBeyondViewport: false,
    fromSurface: true,
  });
  await writeFile(
    path.join(outputDirectory, filename),
    Buffer.from(screenshot.data, "base64"),
  );
  console.log(`Captured ${locale}/${filename}`);
}

await mkdir(outputDirectory, { recursive: true });
await send("Page.enable");
await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", {
  width: 1920,
  height: 1080,
  deviceScaleFactor: 1,
  mobile: false,
});

const loaded = waitForEvent("Page.loadEventFired");
await send("Page.navigate", { url: pageUrl });
await loaded;
await evaluate(`
  new Promise((resolve, reject) => {
    const started = Date.now();
    const timer = setInterval(() => {
      if (!document.querySelector("#workspace")?.hidden) {
        clearInterval(timer);
        resolve(true);
      } else if (Date.now() - started > 15000) {
        clearInterval(timer);
        reject(new Error("The app did not become ready."));
      }
    }, 100);
  })
`);

await evaluate(`(() => {
  document.querySelector('[data-locale="${locale}"]').click();
  const style = document.createElement("style");
  style.textContent = \`
    * { animation: none !important; scroll-behavior: auto !important; transition: none !important; }
    html { scrollbar-width: none; }
    body::-webkit-scrollbar { display: none; }
  \`;
  document.head.append(style);
})()`);

const copy = locale === "ja"
  ? {
      filename: "インタビュー動画.mp4",
      size: "248.6 MB",
      progressTitle: "文字起こし中",
      progressMessage: "文字起こし中: 64%",
      resultFilename: "インタビュー動画.mp4",
      resultMeta: "インタビュー動画.mp4 / 03:26 / ja / CPU / 言語確度 100%",
      segments: [
        ["00:00 - 00:04", "本日の内容について、順番にご説明します。"],
        ["00:04 - 00:08", "まず最初に、計画を作成する目的を確認していきます。"],
        ["00:08 - 00:13", "数字で表現することで、事業の収益性や成長性を客観的に示せます。"],
        ["00:13 - 00:18", "必要な資金と返済能力を明確にすることも大切です。"],
        ["00:18 - 00:24", "作成した結果はTXTや字幕ファイルとして保存できます。"],
      ],
    }
  : {
      filename: "customer-interview.mp4",
      size: "248.6 MB",
      progressTitle: "Transcribing",
      progressMessage: "Transcribing: 64%",
      resultFilename: "customer-interview.mp4",
      resultMeta:
        "customer-interview.mp4 / 03:26 / en / CPU / language confidence 100%",
      segments: [
        ["00:00 - 00:04", "Welcome. Today we will walk through the key points from this interview."],
        ["00:04 - 00:08", "The recording is processed locally on this computer."],
        ["00:08 - 00:13", "The app automatically detects the spoken language and creates timestamped text."],
        ["00:13 - 00:18", "No API key or complicated model settings are required."],
        ["00:18 - 00:24", "The completed transcript can be exported as TXT, SRT, VTT, or JSON."],
      ],
    };

const sharedSetup = `
  document.body.style.paddingBottom = "";
  document.querySelector("#setup-panel").hidden = true;
  document.querySelector("#workspace").hidden = false;
  document.querySelector("#progress-panel").hidden = true;
  document.querySelector("#result-panel").hidden = true;
  document.querySelector("#drop-zone").hidden = false;
  document.querySelector("#selected-file").hidden = true;
  document.querySelector("#submit-button").disabled = true;
  window.scrollTo(0, 0);
`;

await evaluate(`(() => { ${sharedSetup} })()`);
await capture("01-ready.png");

await evaluate(`(() => {
  ${sharedSetup}
  document.querySelector("#drop-zone").hidden = true;
  document.querySelector("#selected-file").hidden = false;
  document.querySelector("#file-name").textContent = ${JSON.stringify(copy.filename)};
  document.querySelector("#file-size").textContent = ${JSON.stringify(copy.size)};
  document.querySelector("#submit-button").disabled = false;
  window.scrollTo(0, Math.max(0, document.querySelector("#workspace").offsetTop - 110));
})()`);
await capture("02-file-selected.png");

await evaluate(`(() => {
  document.querySelector("#progress-panel").hidden = false;
  document.querySelector("#result-panel").hidden = true;
  document.querySelector("#submit-button").disabled = true;
  document.querySelector("#progress-title").textContent =
    ${JSON.stringify(copy.progressTitle)};
  document.querySelector("#progress-percent").textContent = "64%";
  document.querySelector("#progress-bar").style.width = "64%";
  document.querySelector("#progress-message").textContent =
    ${JSON.stringify(copy.progressMessage)};
  window.scrollTo(0, Math.max(0, document.querySelector("#workspace").offsetTop - 90));
})()`);
await capture("03-processing.png");

await evaluate(`(() => {
  document.querySelector("#progress-panel").hidden = true;
  const result = document.querySelector("#result-panel");
  result.hidden = false;
  document.body.style.paddingBottom = "520px";
  document.querySelector("#result-meta").textContent =
    ${JSON.stringify(copy.resultMeta)};
  const downloads = document.querySelector("#download-buttons");
  downloads.replaceChildren(
    ...["TXT", "SRT", "VTT", "JSON"].map((format) => {
      const link = document.createElement("a");
      link.className = "download-button";
      link.textContent = format;
      link.href = "#";
      return link;
    }),
  );
  const transcript = document.querySelector("#transcript");
  const segments = ${JSON.stringify(copy.segments)};
  transcript.replaceChildren(
    ...segments.map(([timestamp, content]) => {
      const row = document.createElement("div");
      row.className = "segment";
      const time = document.createElement("span");
      time.className = "timestamp";
      time.textContent = timestamp;
      const text = document.createElement("p");
      text.textContent = content;
      row.append(time, text);
      return row;
    }),
  );
  window.scrollTo(0, Math.max(0, result.offsetTop - 18));
})()`);
await capture("04-result-and-exports.png");

socket.close();
