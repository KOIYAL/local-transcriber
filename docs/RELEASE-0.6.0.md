# 0.6.0 リリース手順（Windows ポータブル版 / macOS DMG）

0.6.0 の目玉は**アプリ内録音とトレイ常駐**（Phase 1 / 対面MTG録音）。
ビルド手順は 0.5.0 と同じ（vendor\modelshelf.exe 同梱・llama-cpp-python）。
リポジトリ側の準備（バージョン更新・README/ストア文言・トレイアイコン生成）は済み。

## 変更点（リリースノート原稿）

### 日本語

**新機能**

- アプリ内マイク録音: ワンボタンで会議を録音し、停止と同時に文字起こしへ。
  録音中は数秒ごとに端末内へ保存されるため、途中でアプリが落ちても
  直前までの音声が残ります。音声は外部に送信されません
- タスクトレイ常駐: 待機・録音中・一時停止・文字起こし中を形の違う
  アイコンで表示。トレイメニューから録音の開始・停止・一時停止・
  保存先フォルダを開く・直近ジョブの確認ができます
- 録音中の安全装置: 無音が30秒続くと警告表示（マイク切断・入力デバイス
  誤選択の検知）。録音中にアプリを終了しようとすると確認ダイアログ
- ウィンドウを閉じてもトレイに常駐し、録音は継続します
- ログイン時の自動起動をトレイメニューから設定可能（既定はオフ）
- 書き出し先フォルダの指定: トレイメニューでフォルダを選ぶと、TXT/SRT/
  VTT/JSON/要約のダウンロードが毎回のダイアログなしでそこへ保存されます
  （未設定なら従来どおり保存ダイアログ。同名ファイルは連番で回避）

**その他**

- macOSのマイク権限に対応（初回録音時にOSの許可ダイアログが出ます）

### English

**New**

- In-app microphone recording: record a meeting with one button and it flows
  straight into transcription when you stop. Audio is saved to disk every few
  seconds while recording, so a crash never loses more than the last moments.
  Nothing is sent online
- System tray resident: state-shaped icons for idle / recording / paused /
  transcribing, with tray controls for start, pause, stop, opening the data
  folder, and the latest job
- Recording safeguards: a warning appears after 30 seconds of silence
  (unplugged or wrong microphone), and quitting mid-recording asks for
  confirmation
- Closing the window now minimizes to the tray; recording continues
- Optional start-at-login toggle in the tray menu (off by default)
- Configurable export folder: pick a folder from the tray menu and every
  TXT/SRT/VTT/JSON/summary download saves there without a dialog (leave it
  unset to keep the save dialog; name clashes get numbered suffixes)

**Also**

- macOS microphone permission support (the OS permission prompt appears the
  first time you record)

## Windows 側でやること

1. `git pull`
2. `vendor\modelshelf.exe` を配置（手順は [RELEASE-0.5.0.md](RELEASE-0.5.0.md) と同じ）
3. `build-windows.cmd` → `dist\LocalTranscriber-0.6.0-win-x64.zip`
4. **実機スモーク（C7・必須）**:
   - トレイアイコンが出る・状態で形が変わる（待機→録音中→文字起こし中）
   - 録音開始→30秒話す→停止→文字起こし結果が出る
   - 一時停止/再開・録音破棄・無音警告（マイクをミュートして30秒）
   - ウィンドウを閉じる→トレイから再表示・録音中に終了→警告ダイアログ
   - トレイメニュー: 保存先フォルダ・直近ジョブ・自動起動チェックボックス
   - 書き出し先フォルダ: トレイで設定→TXTダウンロードが無ダイアログで
     そのフォルダへ入る・「毎回選ぶに戻す」でダイアログ復帰
5. zipをGitHub Releasesへ（**リリース公開は人間承認**）

## macOS 側でやること

[MAC_RELEASE.md](../MAC_RELEASE.md) の手順どおり。0.6.0 では追加で:

- 初回録音時にマイク許可ダイアログが出ること（NSMicrophoneUsageDescription）
- 許可を拒否した場合にアプリ内にエラートーストが出ること
- メニューバーのテンプレートアイコンがライト/ダーク両方で見えること

## 既知の制限（Phase 1の割り切り）

- macOS配布は **Apple Siliconのみ**（2026-08-03オーナー決定。Intel版は
  需要が見えるまで作らない。要約のApple IntelligenceはもともとApple
  Silicon限定のため機能差も生じない）

- 録音セッションは同時に1つ
- 録音の入力はマイクのみ（システム音声・オンライン会議の相手音声は
  Phase 2 で検討）
- トレイの状態反映は1秒ポーリング
