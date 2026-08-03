## 0.6.0 — 会議録音とトレイ常駐 / Meeting recording and tray resident

### 新機能（日本語）

- **アプリ内マイク録音**: ワンボタンで会議を録音し、停止と同時に文字起こしへ。録音中は数秒ごとに端末内へ保存されるため、途中でアプリが落ちても直前までの音声が残ります。音声は外部に送信されません
- **タスクトレイ常駐**: 待機・録音中・一時停止・文字起こし中を形の違うアイコンで表示。トレイから録音の開始・停止・一時停止・保存先を開く・直近ジョブの確認ができます。ウィンドウを閉じても録音は継続します
- **録音の安全装置**: 無音が30秒続くと警告（マイク切断の検知）。録音中に終了しようとすると確認ダイアログ
- **マイクの選択**: 録音欄のドロップダウンで入力デバイスを指定。選択は記憶され、外れていたら既定へフォールバック
- **書き出し先フォルダの指定**: トレイまたはアプリ内設定で一度選べば、TXT/SRT/VTT/JSON/要約が毎回のダイアログなしでそこへ保存されます
- **文字起こしモデルの手動アップグレード**: 「より良いモデルを確認」ボタンで、このPCに合う上位モデルがあるときだけ確認つきで切替（自動では切り替えません）
- macOSのマイク権限に対応。ログイン時自動起動の設定（既定オフ）

### What's new (English)

- **In-app meeting recording**: one button records from the microphone and flows straight into transcription on stop. Chunks are saved to disk every few seconds, so a crash never loses more than the last moments. Nothing is sent online
- **System tray resident**: state-shaped icons (idle / recording / paused / transcribing), tray controls, and recording continues with the window closed
- **Safeguards**: a 30-second silence warning and a quit confirmation while recording
- **Microphone picker** with remembered choice and automatic fallback
- **Configurable export folder**: set once (tray or in-app Settings) and every export saves there without a dialog
- **Manual model upgrade**: switches to a larger Whisper model only when one fits this computer and you confirm
- macOS microphone permission support; optional start-at-login (off by default)

### ダウンロード / Downloads

- Windows: `LocalTranscriber-0.6.0-win-x64.zip`（ポータブル・展開して `LocalTranscriber.exe`）
- macOS (Apple Silicon): DMGは後日添付（クラウドビルド完了後）
