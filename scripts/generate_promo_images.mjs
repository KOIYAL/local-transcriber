// Generate store promotional images by rendering HTML with headless Chrome.
//
// Usage:
//   CHROME=/path/to/chrome node scripts/generate_promo_images.mjs
//
// Inputs:  assets/app-icon.png, store-assets/screenshots/<locale>/*.png
// Outputs: store-assets/promo/<locale>/hero-2400x1200.png
//          store-assets/promo/<locale>/steps-1920x1080.png
//
// Requires the store screenshots to exist (see capture_store_screenshots.mjs)
// and the Inter / Noto Sans JP fonts to be installed on the system.

import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync, mkdtempSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const CHROME = process.env.CHROME || "google-chrome";
const SCREENSHOTS = path.join(ROOT, "store-assets", "screenshots");
const PROMO = path.join(ROOT, "store-assets", "promo");
const ICON = path.join(ROOT, "assets", "app-icon.png");

const COPY = {
  "ja-JP": {
    appName: "文字起こし",
    heroTitle: "音声と動画を、<br><em>手元で文字に。</em>",
    heroSub: "APIキーもサブスクリプションも不要。文字起こしは、すべてこのPCの中で完結します。",
    badges: ["ローカル処理", "買い切り", "TXT・SRT・VTT・JSON", "日本語・英語UI"],
    footer: "Powered by 株式会社KOIYAL",
    stepsTitle: "かんたん3ステップ",
    steps: [
      ["ファイルを選ぶ", "音声・動画をドラッグ＆ドロップ"],
      ["自動で文字起こし", "PCに合うAIモデルを自動選択"],
      ["確認して書き出す", "TXT・SRT・VTT・JSONで保存"],
    ],
  },
  "en-US": {
    appName: "Local Transcriber",
    heroTitle: "Turn audio and video<br><em>into text, privately.</em>",
    heroSub: "No API key. No subscription. Transcription runs entirely on your computer.",
    badges: ["Local processing", "One-time purchase", "TXT / SRT / VTT / JSON", "Works offline"],
    footer: "Powered by KOIYAL, K.K.",
    stepsTitle: "Three simple steps",
    steps: [
      ["Pick a file", "Drag & drop audio or video"],
      ["Automatic transcription", "The right AI model is chosen for your PC"],
      ["Review and export", "Save as TXT, SRT, VTT, or JSON"],
    ],
  },
};

const BASE_CSS = `
  * { margin: 0; padding: 0; box-sizing: border-box; }
  html, body { width: 100%; height: 100%; overflow: hidden; }
  body {
    font-family: Inter, "Noto Sans JP", sans-serif;
    background:
      radial-gradient(circle at 18% 12%, rgba(129, 140, 248, 0.35), transparent 42rem),
      linear-gradient(135deg, #4338ca 0%, #312e81 55%, #1e1b4b 100%);
    color: #fff;
  }
  em { font-style: normal; color: #fbbf24; }
  .badges { display: flex; flex-wrap: wrap; gap: 14px; }
  .badge {
    padding: 12px 26px;
    border: 1px solid rgba(255, 255, 255, 0.35);
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
    font-size: 26px;
    font-weight: 600;
  }
  .window {
    background: #fff;
    border-radius: 18px;
    overflow: hidden;
    box-shadow: 0 60px 140px rgba(10, 8, 40, 0.55);
  }
  .window img { display: block; }
`;

function heroHtml(locale, copy) {
  const shot = path.join(SCREENSHOTS, locale, "04-result-and-exports.png");
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    ${BASE_CSS}
    body { width: 2400px; height: 1200px; position: relative; }
    .left { position: absolute; left: 130px; top: 120px; width: 1050px; }
    .brand { display: flex; align-items: center; gap: 28px; margin-bottom: 90px; }
    .brand img { width: 120px; height: 120px; border-radius: 27px;
      box-shadow: 0 20px 50px rgba(10, 8, 40, 0.45); }
    .brand span { font-size: 52px; font-weight: 800; letter-spacing: -0.02em; }
    h1 { font-size: 108px; font-weight: 800; line-height: 1.16; letter-spacing: -0.045em; }
    .sub { margin: 48px 0 56px; max-width: 950px; font-size: 38px; line-height: 1.6;
      color: rgba(255, 255, 255, 0.82); }
    .footer { position: absolute; left: 130px; bottom: 70px; font-size: 26px;
      color: rgba(255, 255, 255, 0.55); }
    .window { position: absolute; left: 1290px; top: 240px; width: 1400px;
      height: 720px; }
    .window img { width: 2400px; margin: -20px 0 0 -500px; }
  </style></head><body>
    <div class="left">
      <div class="brand"><img src="file://${ICON}"><span>${copy.appName}</span></div>
      <h1>${copy.heroTitle}</h1>
      <p class="sub">${copy.heroSub}</p>
      <div class="badges">${copy.badges.map((b) => `<span class="badge">${b}</span>`).join("")}</div>
    </div>
    <div class="window"><img src="file://${shot}"></div>
    <p class="footer">${copy.footer}</p>
  </body></html>`;
}

function stepsHtml(locale, copy) {
  // Crop settings: [screenshot file, zoomed image width, x offset, y offset]
  const crops = [
    ["01-ready.png", 960, -200, -240],
    ["03-processing.png", 960, -200, -48],
    ["04-result-and-exports.png", 960, -200, -8],
  ];
  const cards = copy.steps
    .map(([title, sub], index) => {
      const [file, zoom, dx, dy] = crops[index];
      const shot = path.join(SCREENSHOTS, locale, file);
      return `<div class="card">
        <div class="step-no">${index + 1}</div>
        <h2>${title}</h2>
        <p>${sub}</p>
        <div class="window shot"><img src="file://${shot}"
          style="width:${zoom}px;margin:${dy}px 0 0 ${dx}px"><i></i></div>
      </div>`;
    })
    .join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>
    ${BASE_CSS}
    body { width: 1920px; height: 1080px; padding: 90px 100px; }
    .top { display: flex; align-items: center; gap: 22px; margin-bottom: 70px; }
    .top img { width: 76px; height: 76px; border-radius: 17px; }
    .top h1 { font-size: 64px; font-weight: 800; letter-spacing: -0.03em; }
    .cards { display: flex; gap: 48px; }
    .card { width: 560px; }
    .step-no { width: 64px; height: 64px; border-radius: 50%; background: #fbbf24;
      color: #1e1b4b; font-size: 34px; font-weight: 800; display: grid;
      place-items: center; margin-bottom: 26px; }
    .card h2 { font-size: 40px; font-weight: 750; margin-bottom: 12px;
      letter-spacing: -0.02em; }
    .card p { font-size: 26px; color: rgba(255, 255, 255, 0.75); margin-bottom: 34px;
      min-height: 76px; line-height: 1.5; }
    .shot { width: 560px; height: 380px; position: relative; }
    .shot i { position: absolute; left: 0; right: 0; bottom: 0; height: 80px;
      background: linear-gradient(rgba(255, 255, 255, 0), #fff); }
  </style></head><body>
    <div class="top"><img src="file://${ICON}"><h1>${copy.stepsTitle}</h1></div>
    <div class="cards">${cards}</div>
  </body></html>`;
}

function render(html, width, height, outputPath) {
  const workDir = mkdtempSync(path.join(tmpdir(), "promo-"));
  const htmlPath = path.join(workDir, "page.html");
  writeFileSync(htmlPath, html);
  execFileSync(CHROME, [
    "--headless", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
    "--force-device-scale-factor=1",
    `--window-size=${width},${height}`, `--screenshot=${outputPath}`,
    `file://${htmlPath}`,
  ], { stdio: "pipe" });
  console.log(`Wrote ${outputPath}`);
}

for (const [locale, copy] of Object.entries(COPY)) {
  const outDir = path.join(PROMO, locale);
  mkdirSync(outDir, { recursive: true });
  render(heroHtml(locale, copy), 2400, 1200, path.join(outDir, "hero-2400x1200.png"));
  render(stepsHtml(locale, copy), 1920, 1080, path.join(outDir, "steps-1920x1080.png"));
}
