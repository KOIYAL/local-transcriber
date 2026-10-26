## Local Transcriber 0.7.3

更新の確認と、困ったときの原因の調べやすさを良くしました。

### 変わったこと

- **設定に「アップデートを確認」**: 押すと、新しいバージョンがあるかをすぐに確かめ、続けてこの PC に合う上位の文字起こしモデルがあるかも確かめます。新しいバージョンがあれば、ダウンロードページを開くか確認します。
- **設定にバージョンを表示**: 今使っているバージョンが分かるようにしました。
- **設定に「ログフォルダを開く」（Windows・Mac・Linux のアプリ）**: 処理の記録（`backend.log`）を残すようにしました。うまく動かないときは、このフォルダのファイルを添えてお問い合わせください。記録には音声・文字起こしの本文・用語集・要約・ファイル名を含めません。
- **処理が進まないときに記録を残す**: 文字起こしなどが 5 分以上進まないと、その時点の状態を記録します。
- **文字起こしエンジンとの接続が切れたら画面で知らせる**: 進み具合の表示のまま止まらず、再起動を案内します。
- **話者分離の待ち時間を録音の長さに合わせる**: 長く待ち続けず、時間内に終わらなければ話者なしの結果を表示します。
- 設定・用語集・ダウンロード済みのモデルはそのまま使えます。

### 配布物

- Windows 10 / 11 (x64): `LocalTranscriber-0.7.3-win-x64.zip`
- macOS Apple Silicon: `LocalTranscriber-macOS-arm64.dmg`（未署名。初回は「システム設定」→「プライバシーとセキュリティ」→ 一番下の「セキュリティ」の「開く」→「このまま開く」で許可します）
- Linux x86_64（テストビルド）: `LocalTranscriber-0.7.3-linux-x64.tar.gz`

---

## Local Transcriber 0.7.3 (English)

- **"Check for updates" in Settings**: checks for a new app version right away, then for a better transcription model for this computer. If a new version exists, it offers to open the download page.
- **Version shown in Settings.**
- **"Open logs folder" in Settings (desktop apps)**: the app now keeps an operational log (`backend.log`). Attach these files when reporting a problem. Logs never contain audio, transcripts, the glossary, summaries or file names.
- **A record when processing stalls**: if transcription makes no progress for 5 minutes, the app records its state.
- **Lost connection to the engine is shown** instead of a frozen progress bar.
- **Speaker separation waits in proportion to the recording** and shows the transcript without speakers if it does not finish in time.
- Settings, the glossary and downloaded models are kept.
