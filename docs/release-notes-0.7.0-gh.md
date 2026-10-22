## 0.7.0 オンライン会議の音声・用語集・話者分離 / Meeting audio, glossary and speaker separation

### 新機能（日本語）

- **オンライン会議の音声**: PC で再生中の相手の声とマイクを合わせて録音できます。デフォルトは OFF。Windows 10/11 と macOS 14.2以降のパッケージアプリが対象です。ブラウザでは共有機能と共有元によります。取得できなければ理由を表示し、マイク録音を続けます。映像は保存しません。
- **用語集**: 社名・人名・製品名を最大500文字まで保存し、ファイルと録音の文字起こしで参考にします。長い音声の各処理区間に反映します。デスクトップでは用語集・マイク・表示言語・PC音声の設定を、起動時のポートが変わっても保持します。
- **話者分離（試験的・任意）**: 結果・全文コピー・TXT/SRT/VTT/JSON に「話者1」「話者2」などの番号を付けます。対応する依存と8 GiB以上のメモリが必要です。デフォルトは OFF。初回に約46.6 MBの専用モデルを取得し、以後はCPUでオフライン処理します。名前の特定は行わず、短い交代や同時発話では誤る場合があります。
- **Turbo の自動選択**: メモリ32GB以上の新規セットアップで Turbo（large-v3-turbo、約1.62GB）を選択します。導入済みの Medium などは維持し、設定から任意で更新できます。同じ文が何度も繰り返される問題も抑制しました。
- **新版の確認**: 画面とトレイに新版のリンクを表示します。GitHub API への1回の取得結果を、失敗時も24時間キャッシュします。`LT_UPDATE_CHECK=off`（`0` / `false` / `no` も可）で停止できます。自動更新は行いません。
- **Linux x64 テストビルド**: Ubuntu 22.04以降を対象に、tar.gz のビルドと CI を追加しました。Linux ではウィンドウを閉じると終了し、録音・一時停止中は確認します。PC音声とログイン時自動起動は非表示です。Ubuntu 22.04 の CI では modelshelf を同梱できないため、通常は要約も非表示です。
- **Microsoft Store 用の準備**: Windows CI で未署名 MSIX を作成できます。識別情報と提出番号が未設定なら MSIX だけをスキップします。Store の商品名と買い切り方針は変更せず、申請・公開は別途行います。

### 修正・安定性（日本語）

- ローカル API の Host・書き込み要求の Origin を確認し、DNS rebinding・CSRF への対策を追加。大きすぎるアップロードは Content-Length がある場合に multipart 解析前にも拒否します。
- 録音チャンクの送信を最大3回まで試し、失敗を警告します。停止・初期化に失敗したセッションを解放し、ページ再読み込み後の孤立した録音は停止して文字起こしに回します。
- 文字起こしの失敗・中断時は元音声を残します。話者分離も別プロセスで行い、API応答や録音チャンクの保存を妨げないようにしました。分離の失敗・異常終了・1時間の制限時間超過では、通常の文字起こし・書き出し・元音声を保持します。
- Apple Intelligence の長文要約で処理が終わらなくなる問題を修正。ジョブ一覧は本文・要約を含めず、古い完了・失敗ジョブを50件超過時に一覧から外します。出力ファイルは残ります。
- 導入済みモデルを起動時に優先し、上位モデルの更新候補を正しく表示。切り替え前のモデルがメモリに残る問題も修正しました。
- CUDA の計算精度を自動選択し、デフォルトの自動デバイス設定では対応しない GPU・ランタイムのエラー時に CPU で再試行します。
- バックエンドの起動失敗をダイアログに表示し、起動待ちを90秒に延長。終了時に文字起こしスレッドが残る問題を修正しました。
- Electron のページ遷移先をバックエンドと同じオリジンに限定。PC音声の取得ではオリジンの末尾スラッシュによる誤拒否を修正しました。

音声・用語集・文字起こし・要約を外部へ送りません。初回準備や利用者が選んだモデル更新ではダウンロードが発生します。準備後の推論はオフラインで行えます。新版確認は GitHub API に本文を含まないリクエストを送り、環境変数で停止できます。

### What's new (English)

- **Online meeting audio**: optionally mix computer playback with your microphone. Off by default; available in Windows 10/11 apps and packaged macOS 14.2+ apps. Browser support depends on the sharing API and source. Capture failures explain the problem and continue with the microphone. Video is never saved.
- **Glossary**: save up to 500 characters of company, people and product names for files and recordings. Terms reach every processing window in long audio. Desktop glossary, microphone, language and computer-audio preferences now persist across restarts and backend port changes.
- **Experimental speaker separation**: optional numbered speaker labels in results, copied text and TXT/SRT/VTT/JSON. Requires a working optional dependency and at least 8 GiB RAM. Off by default; first use downloads about 46.6 MB of models, then runs offline on CPU. Labels do not identify people, and short turns or overlapping speech can be misassigned.
- **Turbo model selection**: new setups on computers with at least 32 GB RAM choose Turbo (large-v3-turbo, about 1.62 GB). Installed models, including Medium, are kept; upgrades remain optional in Settings. Repeated-text loops are also reduced.
- **Release notifications**: page and tray links for newer releases. One GitHub API fetch is cached for 24 hours, including failures. Set `LT_UPDATE_CHECK=off` (`0`, `false` or `no` also work) to disable it. No automatic app updates.
- **Linux x64 test builds**: tar.gz packaging and CI targeting Ubuntu 22.04+. Closing the window quits on Linux, with confirmation while recording or paused. Computer audio and start-at-login are hidden. Ubuntu 22.04 CI omits modelshelf, so summaries are normally hidden too.
- **Microsoft Store preparation**: Windows CI can produce an unsigned MSIX. Missing identity or submission-version settings skip only the MSIX. The Store product name and one-time-purchase policy are unchanged; submission and publication remain separate steps.

### Fixes and reliability (English)

- Validate local API Host and write-request Origin headers against DNS rebinding and CSRF. Reject oversized uploads with a known Content-Length before multipart parsing as well.
- Try recording chunk uploads up to three times and warn on failure. Clean up sessions after failed initialization or stopping; recover orphaned recordings after page reload by stopping and transcribing them.
- Retain source audio after failed or interrupted transcription. Speaker separation runs in a separate process to keep the API and recording chunk saves responsive. Failure, abnormal exit or the one-hour timeout preserves the ordinary transcript, exports and source audio.
- Bound Apple Intelligence's long-text reduction loop. Job lists omit transcript and summary bodies and evict older completed/failed entries above 50 jobs while keeping output files.
- Prefer installed models at startup, correctly offer upgrades, and release the previous model when switching.
- Select CUDA compute precision automatically. With the default automatic device setting, unsupported GPU/runtime errors retry on CPU.
- Show backend startup errors in a dialog, allow 90 seconds for startup, and fix transcription threads preventing shutdown.
- Restrict Electron navigation to the backend origin and fix computer-audio capture being rejected because of a trailing slash in the origin.

Audio, glossary entries, transcripts and summaries stay on the computer. Initial setup and user-selected model upgrades download model files. Inference works offline after setup. Release checks send a content-free request to GitHub and can be disabled with the environment variable above.

### ダウンロード / Downloads

- Windows x64: `LocalTranscriber-0.7.0-win-x64.zip`（展開して `LocalTranscriber.exe` を起動 / extract and run）
- macOS Apple Silicon: `LocalTranscriber-macOS-arm64.dmg`（アプリ内バージョン0.7.0・未署名のテストビルド / app version 0.7.0, unsigned test build）
- Linux x64: `LocalTranscriber-0.7.0-linux-x64.tar.gz`（テスト配布 / test build）

macOS の PC音声にはマイク・画面収録・システム音声の権限が必要です。Bluetooth 使用時は入出力デバイスや音質が変わることがあります。Linux のトレイには AppIndicator 対応が必要です。話者分離と要約は対応環境だけに表示します。未署名 MSIX は Store 提出用で、一般向けダウンロードには含めません。

On macOS, computer audio needs microphone, screen-recording and system-audio permissions. Bluetooth headsets can change devices or audio quality. The Linux tray requires AppIndicator support. Speaker separation and summaries appear only on supported systems. Unsigned MSIX files are for Store submission, not general downloads.
