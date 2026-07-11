# Discord Rich Presence

Local Transcriber 起動中、ユーザーの Discord プロフィールに「Local Transcriber をプレイ中」として
アクティビティが表示される任意機能です（`app/discord_presence.py`）。

## プライバシー

- 表示されるのは**汎用ステータスのみ**（「起動中」「音声を文字起こし中」＋「完全ローカル処理・外部送信なし」）。
  **ファイル名・文字起こし内容・ユーザーデータは一切表示しません**（回帰テストあり）
- 通信は同一PC内の Discord デスクトップアプリとのローカルIPCのみ。外部サーバーへの送信はありません
- Discord 未起動・未インストールなら何も起きません（全経路 no-op）

## 無効化

環境変数 `LT_DISCORD_PRESENCE=off` で完全に無効になります。

## セットアップ（HUMAN NEEDED・未完了）

- [ ] [Discord Developer Portal](https://discord.com/developers/applications) で **Local Transcriber 専用アプリ**を作成
      （他アプリと使い回さない。表示名＝アプリ名になるため）
- [ ] General Information → **Application ID** を `app/discord_presence.py` の `APP_ID` へ記入
- [ ] Rich Presence → **Art Assets** にアプリアイコンをキー名 **`logo`** で登録（512×512以上。`assets/` のアイコン流用可）
- [ ] Windows / macOS の実機で Discord を起動した状態で表示確認

## 設計メモ

- 書き込み専用IPC＋定期再接続（UPDATE_SEC=30 / RECONNECT_SEC=240 / RETRY_SEC=60）。
  根拠はモジュール先頭のdocstring参照（KOIYALの godot-discord-presence と同一の設計判断）
- Windows は named pipe、macOS/Linux は unix socket（`XDG_RUNTIME_DIR` → `TMPDIR` → `/tmp` の順で探索）
- 本機能は Discord 非公式です。Discord は Discord Inc. の商標です
