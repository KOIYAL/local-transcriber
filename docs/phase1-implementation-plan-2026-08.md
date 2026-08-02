# Phase 1 実装計画: 対面MTG録音ボタン＋トレイ常駐（2026-08-03起票）

> 正本要件: `realtime-meeting-feasibility-2026-07.md` §5 Phase 1 ＋ 追補（トレイ常駐・2026-07-29オーナー指示）。
> 見積: 3〜5人日＋常駐1〜2人日。**コミット単位で中断再開できる**よう工程を分割する（各コミットは単体でアプリが壊れない）。
> リリース（push・GitHub Releases）は人間承認。リリース時に koiya-os 側カレンダーの「Local Transcriber連動枠」を編成する。

## アーキテクチャ方針

- **録音はレンダラ（ブラウザ）側で MediaRecorder により取得**し、チャンクをバックエンドへ逐次アップロードする。バックエンド（FastAPI）は `app/capture.py` でセッション管理し、停止時に1ファイルへ結合して**既存の JobManager 経路（文字起こし→要約）へそのまま合流**させる
- 逐次アップロードにするのは**クラッシュ耐性のため**（Electronが落ちても直前チャンクまでは残り、部分復旧できる。会議は再現できないという追補の前提に対応）
- トレイ常駐は Electron `Tray`。状態はバックエンドの録音ステータスAPIをポーリングして反映（stopped / recording / paused / transcribing / error を**形の違うアイコン**で）
- 無音検知はレンダラの AudioContext でレベル計測し、閾値未満が一定時間続いたら通知＋トレイ警告状態

## コミット計画（C1〜C8）

| # | 内容 | 触るファイル | 目安 |
|---|---|---|---|
| C1 | `app/capture.py`: RecordingSession（作成/チャンク追記/停止→結合→Job投入/破棄）＋単体テスト | app/capture.py, tests/ | 0.5日 |
| C2 | 録音API 3本: `POST /api/recording/start`・`POST /api/recording/{id}/chunk`・`POST /api/recording/{id}/stop`（＋`GET /api/recording/status`） | app/main.py | 0.5日 |
| C3 | 録音UI: `app/static/recorder.js`（開始/一時停止/停止・経過時間・レベルメーター・MediaRecorder→チャンクPOST）＋index組込＋i18n（ja/en） | app/static/ | 1日 |
| C4 | 無音・入力断検知: レベルゼロが30秒続いたら画面通知＋statusへ反映 | recorder.js, capture.py | 0.5日 |
| C5 | Electronトレイ常駐: 状態別アイコン（形で判別・macOSテンプレート画像）・ツールチップに経過時間・メニュー（開始/停止/一時停止/保存先/直近ジョブ）・**録音中の終了警告**・自動起動は既定オフ | desktop/main.js, assets/tray/ | 1〜1.5日 |
| C6 | macOSマイク権限: entitlements＋Info.plist（NSMicrophoneUsageDescription）・権限拒否時のエラー表示 | desktop/, backend.spec | 0.5日 |
| C7 | 実機スモーク: Windows実機（人間）・macOSはクラウドMacビルド（CLOUD-MAC-BUILD.md）。録音→文字起こし→要約の通し確認 | - | 1日 |
| C8 | README・ストア文言・スクショ更新＋リリースノート | README*, STORE_SUBMISSION.md | 0.5日 |

並行推奨（正本§5の推奨順1）: **kotoba-whisper-v2.0-faster への差し替え（1〜2人日）**は Phase 1 と独立に価値が立つ。`app/model_manager.py` / `system_info.py` のモデル表更新＋精度スモークで別コミット系列（K1）として扱い、Phase 1 の後に着手判断を仰ぐ。

## 設計上の決定（先に固定する）

1. チャンク形式は `audio/webm;codecs=opus`（MediaRecorder既定）。結合はバイト連結で可（webmはクラスタ追記に耐える。faster-whisper側はffmpeg/av経由でデコードできることをC1のテストで確認する）。不可ならwavフォールバック（AudioWorkletでPCM取得）へ切替
2. 録音セッションは**同時に1つ**（Phase 1の割り切り。UIも単一ボタン）
3. 保存先は既存ジョブと同じディレクトリ構造。録音元ファイルは job の入力として残す（削除は既存の delete に乗る）
4. トレイの状態取得は 1秒ポーリング（バックエンドは既にローカルHTTP。イベント化はPhase 2で検討）
5. **プライバシー文言**: 録音データはローカルのみ・外部送信なし、をUIの録音開始ボタン脇に明記（製品の核）

## 中断再開プロトコル

- 各コミットメッセージは `phase1: C<n> <内容>` 形式
- 次に着手すべきコミットは本ファイルの下の進捗表を正とする

## 進捗

| コミット | 状態 |
|---|---|
| C1 | **完了**（2026-08-03・テスト8本） |
| C2 | **完了**（2026-08-03・APIテスト3本） |
| C3 | **完了**（2026-08-03・フェイクマイクでE2Eスモーク済み・webm連結デコード実証） |
| C4 | **完了**（C1のサーバー追跡＋C3のレベル送信/警告表示で実装） |
| C5 | **完了**（2026-08-03・トレイ常駐＋状態別アイコン5種＋閉じる=トレイ格納＋録音中終了警告＋自動起動既定オフ。アイコンは `desktop/assets/tray/generate_tray_icons.py` で決定論生成。実機でのトレイ表示確認はC7へ） |
| C6 | **完了**（2026-08-03・entitlementsに `com.apple.security.device.audio-input` 追加・`extend-info.mac.plist` で NSMicrophoneUsageDescription（ja/en併記・外部送信なし明記）を Info.plist へ注入。権限拒否時のエラー表示はC3の micDenied トーストが担当。実機TCCプロンプト確認はC7へ） |
| C7 | 未着手（Windows実機は人間） |
| C8 | 未着手 |
