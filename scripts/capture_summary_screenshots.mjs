// Captures README screenshots of the summary feature by staging UI states
// over CDP, in the same way capture_store_screenshots.mjs stages the store
// shots. Usage:
//   node scripts/capture_summary_screenshots.mjs <debug-port> <ja|en> <out-dir>
// with the app running (STORE_SCREENSHOT_APP_URL, default 127.0.0.1:8765)
// and a Chrome listening on <debug-port>.

import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

const [, , debugPort, locale, outputDirectory] = process.argv;
if (!debugPort || !["ja", "en"].includes(locale) || !outputDirectory) {
  console.error(
    "Usage: node capture_summary_screenshots.mjs <debug-port> <ja|en> <output-dir>",
  );
  process.exit(2);
}

const pageUrl = process.env.STORE_SCREENSHOT_APP_URL || "http://127.0.0.1:8765";
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
  width: 1560,
  height: 1000,
  deviceScaleFactor: 1,
  mobile: false,
});

const loaded = waitForEvent("Page.loadEventFired");
await send("Page.navigate", { url: pageUrl });
await loaded;
await sleep(400);

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
      resultMeta: "定例ミーティング.m4a / 00:38 / ja / CPU / 言語確度 100%",
      segments: [
        ["00:00 - 00:06", "えー、本日の定例ミーティングを始めます。まず先週の進捗ですが、新しい要約機能の実装が完了しました。"],
        ["00:06 - 00:12", "テストもすべて通っています。次にリリース時期についてですが、田中さんからは今月末を目標にしたいという提案がありました。"],
        ["00:12 - 00:19", "ただし、佐藤さんからドキュメントの整備がまだ終わっていないという指摘があり、"],
        ["00:19 - 00:26", "議論の結果、ドキュメント完成を優先し、リリースは来月の第一週に延期することで合意しました。"],
        ["00:26 - 00:31", "また、次回のミーティングでは価格プランについて話し合う予定です。"],
        ["00:31 - 00:38", "アクションアイテムは、佐藤さんが金曜までにドキュメントを完成させること、田中さんがリリースノートの下書きを準備することの2点です。"],
      ],
      summarizeLabel: "要約する",
      resummarizeLabel: "もう一度要約",
      preparing: "要約モデルを準備中... 63%",
      summary: [
        "定例ミーティングでは、新しい要約機能の実装とテスト完了が共有され、リリース時期について議論しました。ドキュメント整備を優先するため、リリースは今月末案から来月第1週へ延期することで合意しています。",
        "- 新機能の実装とテストが完了",
        "- リリースは来月第1週に延期（ドキュメント完成を優先）",
        "- 次回は価格プランを議論",
        "- アクション: 佐藤さんが金曜までにドキュメント完成、田中さんがリリースノート下書き",
      ].join("\n"),
      downloads: ["TXT", "SRT", "VTT", "JSON"],
      downloadsAfter: ["TXT", "SRT", "VTT", "JSON", "SUMMARY.TXT"],
    }
  : {
      resultMeta: "weekly-meeting.m4a / 00:38 / en / CPU / language confidence 100%",
      segments: [
        ["00:00 - 00:06", "Let's start the weekly meeting. First, last week's progress: the new summary feature is implemented."],
        ["00:06 - 00:12", "All tests pass. On the release date, Tanaka proposed targeting the end of this month."],
        ["00:12 - 00:19", "However, Sato pointed out that the documentation is not finished yet,"],
        ["00:19 - 00:26", "and we agreed to prioritize the docs and move the release to the first week of next month."],
        ["00:26 - 00:31", "Next meeting we will discuss the pricing plan."],
        ["00:31 - 00:38", "Action items: Sato finishes the docs by Friday, and Tanaka drafts the release notes."],
      ],
      summarizeLabel: "Summarize",
      resummarizeLabel: "Summarize again",
      preparing: "Preparing the summary model... 63%",
      summary: [
        "The weekly meeting covered the completed summary feature and the release schedule. To prioritize documentation, the release moves from end of this month to the first week of next month.",
        "- New feature implemented and tested",
        "- Release postponed to the first week of next month",
        "- Pricing plan on the next agenda",
        "- Actions: Sato finishes docs by Friday, Tanaka drafts release notes",
      ].join("\n"),
      downloads: ["TXT", "SRT", "VTT", "JSON"],
      downloadsAfter: ["TXT", "SRT", "VTT", "JSON", "SUMMARY.TXT"],
    };

const stageResult = (downloads) => `
  document.body.style.paddingBottom = "420px";
  document.querySelector("#setup-panel").hidden = true;
  document.querySelector("#workspace").hidden = true;
  document.querySelector("#progress-panel").hidden = true;
  const result = document.querySelector("#result-panel");
  result.hidden = false;
  document.querySelector("#result-meta").textContent =
    ${JSON.stringify(copy.resultMeta)};
  document.querySelector("#download-buttons").replaceChildren(
    ...${JSON.stringify(downloads)}.map((format) => {
      const link = document.createElement("a");
      link.className = "download-button";
      link.textContent = format;
      link.href = "#";
      return link;
    }),
  );
  const transcript = document.querySelector("#transcript");
  transcript.replaceChildren(
    ...${JSON.stringify(copy.segments)}.map(([timestamp, content]) => {
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
  const section = document.querySelector("#summary-section");
  section.hidden = false;
  document.querySelector("#summary-status").hidden = true;
  document.querySelector("#summary-text").hidden = true;
  document.querySelector("#summary-upgrade").hidden = true;
  const button = document.querySelector("#summarize-button");
  button.disabled = false;
  button.querySelector("span").textContent = ${JSON.stringify(copy.summarizeLabel)};
  window.scrollTo(0, Math.max(0, result.offsetTop - 18));
`;

// 1. A finished transcription with the Summarize button available.
await evaluate(`(() => { ${stageResult(copy.downloads)} })()`);
await capture("summary-1-button.png");

// 2. First run: the model is being provisioned automatically.
// (`button` is declared by the shared staging snippet above.)
await evaluate(`(() => {
  ${stageResult(copy.downloads)}
  button.disabled = true;
  const status = document.querySelector("#summary-status");
  status.textContent = ${JSON.stringify(copy.preparing)};
  status.hidden = false;
})()`);
await capture("summary-2-preparing.png");

// 3. The finished summary, exported as SUMMARY.TXT alongside the others.
await evaluate(`(() => {
  ${stageResult(copy.downloadsAfter)}
  button.querySelector("span").textContent = ${JSON.stringify(copy.resummarizeLabel)};
  const text = document.querySelector("#summary-text");
  text.textContent = ${JSON.stringify(copy.summary)};
  text.hidden = false;
})()`);
await capture("summary-3-result.png");

socket.close();
