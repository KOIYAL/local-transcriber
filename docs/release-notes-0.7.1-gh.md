## Local Transcriber 0.7.1

0.7.0 で文字起こしが失敗する不具合と、Mac 版が開けない不具合を直した修正版です。0.7.0 をお使いの方は入れ直してください。設定・用語集・ダウンロード済みのモデルはそのまま使えます。

### 直したこと

- **文字起こしが必ず失敗する（Windows・macOS・Linux）**: 0.7.0 の配布物は、音声を読み込む部品 PyAV の新しい版（19.0.2）を取り込んでおり、ファイルの文字起こしと録音後の文字起こしが `open() got an unexpected keyword argument 'metadata_errors'` で止まりました。PyAV を 19 より前の版に固定し、実際の音声を読み込むテストを追加しました。
- **Mac で「壊れているため開けません」と表示される**: 未署名ビルドの署名が壊れていたため、macOS が開く手段を出しませんでした。署名を付け直し、ビルドのたびに検証します。
- **Mac で開けても文字起こしが起動しない**: 同梱したバックエンドの中のリンクがビルド用の機械の場所を指していて、Python 本体を読み込めませんでした。リンクをアプリ内に戻しました（Linux 版にも同じリンクがありましたが、こちらは動作に影響していませんでした）。

### Mac の DMG

DMG を開くと、アプリを Applications フォルダへドラッグする画面が出ます。Apple の公証を付けていないため、初回は「Apple は検証できませんでした」と表示されて起動が止まります。次の手順で 1 回だけ許可してください。

1. 警告は「完了」で閉じる
2. 「システム設定」→「プライバシーとセキュリティ」を開き、下の方の「セキュリティ」にある「開く」を押す
3. 確認の画面で「このまま開く」を押し、Mac のログインパスワードを入力する

### 配布物

- Windows 10 / 11 (x64): `LocalTranscriber-0.7.1-win-x64.zip`
- macOS Apple Silicon: `LocalTranscriber-macOS-arm64.dmg`（未署名 / unsigned）
- Linux x86_64（テストビルド）: `LocalTranscriber-0.7.1-linux-x64.tar.gz`

---

## Local Transcriber 0.7.1 (English)

A fix release for 0.7.0. Please reinstall if you use 0.7.0; settings, the glossary and downloaded models are kept.

- **Transcription always failed (Windows, macOS, Linux)**: the 0.7.0 builds bundled PyAV 19.0.2, which removed an argument faster-whisper still uses, so transcription stopped with `open() got an unexpected keyword argument 'metadata_errors'`. PyAV is now pinned below 19 and a test decodes real audio.
- **macOS reported the app as "damaged"**: the unsigned build carried a broken signature. It is now ad-hoc signed and verified on every build.
- **On macOS the transcription backend could not start**: links inside the bundled backend pointed at the build machine, so Python could not be loaded. They now stay inside the app.
- The DMG opens a drag-to-Applications window. The app is not notarized: on first launch close the warning with "Done", then open System Settings > Privacy & Security, click "Open" in the Security section, choose "Open Anyway" and enter your login password.
