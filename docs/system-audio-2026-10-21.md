# オンライン会議録音の実装と実機確認

T2 実装日: 2026-10-21。バージョン表記は T6 まで 0.6.0 のまま。

## 使い方と対応範囲

録音前に「PC で再生中の音声も録る（オンライン会議用）」を ON にする。
デフォルトは OFF。選択は localStorage の `lt.system-audio` に保存する。
録音開始後は「PC 音声あり」を確認する。文字起こしは停止後に実行する。

| 環境 | 扱い |
|---|---|
| Windows 10/11 の Electron | PC の再生音と選択したマイクを録音する |
| macOS 14.2 以降のパッケージ版 | PC の再生音とマイクを録音する。マイク、画面収録、システム音声の収録を許可する |
| macOS 14.2 未満 | トグルを隠す。旧収録方式への切り替えを避け、マイク録音を維持する |
| macOS の開発起動（npm start） | トグルを隠す。起動元のターミナルや IDE の権限説明を保証できないため |
| Linux の Electron | トグルを隠す。今回の loopback の対象に含めない |
| ブラウザ | getDisplayMedia と AudioContext があれば表示する。音声の対応は OS・ブラウザ・共有元次第 |

ブラウザでは会議のタブや画面を選び、音声共有を有効にする。タブ共有はそのタブの音声だけを取る。
デスクトップで PC 全体の再生音を取る場合、通知音や音楽も含まれる。
どちらもマイクの使用許可は必要であり、PC 音声だけの録音には対応しない。
Bluetooth ヘッドセットはマイク使用時に音質や再生先が変わる場合がある。
問題があれば有線ヘッドホンと内蔵または USB マイクで試す。

## 実装上の判断

- `desktop/node_modules/electron/package.json` は 42.4.0。
  `electron.d.ts` で `setDisplayMediaRequestHandler`、`desktopCapturer.getSources`、
  `process.getSystemVersion`、`additionalArguments`、`executeJavaScript` の userGesture 引数を確認した。
- `Streams.audio` の型コメントは Windows のみと記載しているが、同じ 42.4.0 の
  [公式 desktopCapturer 文書](https://github.com/electron/electron/blob/v42.4.0/docs/api/desktop-capturer.md)
  には macOS 14.2 以降の CoreAudio Tap と `NSAudioCaptureUsageDescription` が説明されている。
  この確認済みの経路だけを有効にし、旧方式への Chromium フラグ変更は行わない。
- `extend-info.mac.plist` に `NSAudioCaptureUsageDescription` と `NSScreenCaptureUsageDescription` を追加した。
  `build-macos.sh` はこのファイルを `--extend-info` で取り込む。
  既存の `com.apple.security.device.audio-input` entitlement を使い、未確認の権限キーは足さない。
- OS の対応判定は main から preload へ引数で渡し、
  `window.localTranscriber.systemAudio = {supported, reason}` として公開する。
  非対応環境ではトグルを隠す。保存済みの ON も使わない。
- Electron はバックエンドと同じオリジンのメインフレームから、利用者の操作で音声・映像を要求した場合だけ許可する。
  画面の一覧取得後にも再確認する。取得失敗・画面なしは必ず拒否を返す。
  トレイの録音操作も利用者の操作として渡す。
- ブラウザの操作権限を失わないように、録音ボタンから最初に `getDisplayMedia` を呼び出す。
  映像トラックは即座に停止する。マイクと PC 音声を AudioContext の録音用出力に接続し、
  同じ合成音を MediaRecorder とメーターに渡す。スピーカーには接続しない。
- 拒否・キャンセル・音声なし・合成失敗ではトグルを OFF に戻して保存し、日英の理由を表示する。
  途中で共有が終わった場合も、PC 音声の接続を外しマイクだけで録音を続ける。
- 停止・破棄・開始失敗時はマイク、PC 音声、合成後のトラックと AudioContext を解放する。
  停止後の保存処理を待つ間も収録を続けない。
  音声のアップロードは従来どおり端末内の `/api/recording/*` に限る。映像は保存・送信しない。
- 任意項目のトレイツールチップは追加しない。録音パネルの「PC 音声あり」で取得状態を示す。

## 自動検証

```sh
.venv/bin/python -m pytest -q
node --test tests/system_audio.test.cjs
node --check app/static/recorder.js
node --check desktop/main.js
node --check desktop/preload.js
node --check desktop/system-audio.js
bash -n build-macos.sh
```

Node のテストは標準の test / vm を使い、DOM、MediaDevices、AudioContext、MediaRecorder、
fetch、Electron を偽物に置き換える。実モデル、実音声、ネットワーク、OS の録音権限には触れない。
デフォルト OFF、設定保存、非対応環境、音声合成とメーター、共有失敗、共有終了、マイク失敗、
録音開始失敗、一時停止・再開・停止・破棄、二重開始防止、preload、Electron の許可条件を確認する。

## 人が確認すること（未実施）

この開発環境では Windows / macOS の実機録音、DMG のビルドと権限ダイアログ、
ブラウザの実際の共有画面は検証していない。以下を公開前に確認する。

1. Windows 10/11 と macOS 14.2 以降のパッケージ版を起動し、初期状態ではマイクだけを録音できること。
2. Mac のアプリ内 Info.plist に音声と画面収録の説明が入っていること。
   初回の権限要求を許可する。拒否した場合、OS の「プライバシーとセキュリティ」で
   マイク・画面収録・システム音声の収録を許可してアプリを再起動する。
3. Zoom / Teams / Meet で、相手だけが話す時間と自分だけが話す時間を作る。
   ON のとき両方が録音・文字起こしに入ること。ヘッドホンでスピーカー経由の混入を避ける。
   「PC 音声あり」はトラック取得の表示であり、無音ではないことの保証にはならない。
   特に Mac の権限不足では音声トラックが無音のまま返る場合があるため、相手だけの音を確認する。
4. ブラウザ（Chrome / Edge など）のタブ共有と画面共有で、音声共有の ON/OFF をそれぞれ試す。
   キャンセル・音声なしでは理由が出て OFF に戻り、マイクだけで続けられること。
5. 録音途中に共有を終了し、通知とマイク録音の継続を確認する。
   一時停止・再開・停止・破棄後に、OS の収録表示が終了すること。
6. トレイからの開始・停止、ウィンドウを閉じてトレイに隠した状態での継続、再度の録音を試す。
7. Bluetooth ヘッドセットと有線機器で再生先・音質・二重録音を確認する。
   日本語と英語でトグル、通知、「PC 音声あり」を確認する。

公式の確認元:
[Electron 42.4.0 desktopCapturer](https://github.com/electron/electron/blob/v42.4.0/docs/api/desktop-capturer.md)、
[Electron session](https://www.electronjs.org/docs/latest/api/session#sessetdisplaymediarequesthandlerhandler-opts)、
[getDisplayMedia](https://developer.mozilla.org/en-US/docs/Web/API/MediaDevices/getDisplayMedia)。
