# 0.7.0 実装計画（2026-10-21 起票）

オーナー指示（2026-10-21）: 改善案 1〜8 をすべて行う。PC の環境に合わせて機能を制限してよい。
実装は Codex が行い、Claude は計画・検証・コミット確認・公開を担当する。

## 全タスク共通のルール

- リポジトリは `/home/zenkutsu/local-transcriber`。Python は `.venv/bin/python`（3.12）。
  依存を足したら `.venv/bin/pip install -e ".[dev,<extra>]"` で入れる。
- **`pytest` は常に通す**（`.venv/bin/python -m pytest -q`）。テストはネットワーク・実モデル・外部バイナリに
  触らない（`tests/test_llm_manager.py` の偽物パターン）。新しい外部連携には必ず差し替え口と偽物を用意する。
- UI の文言は `app/static/app.js` / `app/static/recorder.js` の `ja` と `en` の両方に入れる。
- コード内コメントは英語。ドキュメント（`docs/`, `README.ja.md`）は日本語。`README.md` は英語。
- 日本語の文書は `/home/zenkutsu/koiya-os/writing/word-choices.md` の言い換え表に従う
  （「デフォルト」「保存先」のような本人の言い方を使う）。ダッシュ記号は日本語の文に使わない。
- 機能はすべて**任意**で、対応しない環境では UI に出さない（隠す）か、理由を表示する。
  デフォルトの動作は 0.6.0 と同じであること。
- プライバシーの約束を守る: 音声・文字起こし・要約を外へ送らない。外へ出す通信は
  「新版の確認（GitHub API への 1 リクエスト）」だけで、環境変数で止められること。
- 1 タスク 1 コミット（必要なら数コミット）。`git add` は**ファイル名を指定**する（`-A` や `.` は使わない）。
  コミットメッセージは英語の Conventional Commits（`feat:` / `fix:` / `ci:` / `docs:`）。末尾に次の 2 行:
  ```
  Co-Authored-By: Codex <noreply@openai.com>
  Claude-Session: https://claude.ai/code/session_018ZAfWfqFni9nq3T8kXVXyZ
  ```
- 未追跡の `scripts/transcribe_cli.py` はオーナーの個人用スクリプト。触らない・コミットしない。
- タスクの最後に `docs/plan-0.7.0-2026-10-21.md` の「進捗」表を更新する（何をしたか・残したこと・人がやること）。

## 背景（なぜこの順か）

- Search Console: `local transcriber` 1.4 位、`文字起こし ローカル` 3.5 位、`完全ローカル文字起こし` 6.5 位（表示 196）。
- 0.6.0 のダウンロード: Windows 844 / macOS 111。Windows 版は CUDA を同梱していないので、ほぼ全員が CPU 実行。
- 競合との最大の差は「オンライン会議の音声を取れない」こと（`docs/realtime-meeting-feasibility-2026-07.md` §2）。

## T1 エンジンと小さな改善（半日）

1. `app/transcriber.py`: `condition_on_previous_text=False`。理由をコメントに書く
   （会議録音では同じ文の繰り返しが何分も続く事故を防ぐ。表記ゆれは用語集で補う）。
2. **turbo を最上位の自動選択に**: `app/system_info.py` の `select_model_for_memory` で 32GB 以上を `"turbo"`
   （faster-whisper の `large-v3-turbo`。medium より速く精度も上）。`app/model_manager.py` の
   `MODEL_DOWNLOAD_BYTES` に turbo（約 1.6GB。`faster_whisper.utils._MODELS` と Hugging Face の実サイズを確認して書く）、
   `MODEL_QUALITY_ORDER` の末尾に `"turbo"`。medium は残す（入っている人はアップグレード候補になる）。
   `app/config.py` の MODEL_PRESETS の説明文も直す。README 2 本のメモリ表を更新。
3. **用語集（initial_prompt）**: 画面に「用語集（社名・人名・製品名）」の textarea を追加（`app/static/index.html`・`app.js`。
   localStorage に保存）。`POST /api/jobs` と `POST /api/recording/{id}/stop` に form 項目 `glossary` を追加し、
   バックエンドで `options["initial_prompt"]` に入れる（前後の空白を除き、500 文字で切る。Whisper の prompt 上限は
   224 トークン）。テスト: glossary が options に乗ること、長すぎる入力が切られること。
4. **新版の確認**: `GET /api/update-check` を追加。GitHub の
   `https://api.github.com/repos/KOIYAL/local-transcriber/releases/latest` を `urllib` で 5 秒タイムアウトで 1 回取得し、
   `data_dir/update-check.json` に 24 時間キャッシュ。返す形は
   `{"current": "0.7.0", "latest": "0.7.1", "url": "...", "update_available": true, "checked": true}`。
   環境変数 `LT_UPDATE_CHECK=off`（0/false/no も）で無効（`checked: false`）。取得失敗は `checked: false` で静かに返す。
   取得関数は差し替え可能にし、テストは偽物で行う。UI は画面上部に 1 行のお知らせ（リンクは `target="_blank"`。
   Electron は https を外部ブラウザで開く設定済み）。Electron のトレイにも「新しいバージョン x.y.z」項目
   （`desktop/main.js` の `pollBackendState` で 1 時間に 1 回だけ問い合わせ）。
   README 2 本の環境変数表と「データの扱い」に、この通信と止め方を書く。
5. バージョン表記はまだ 0.6.0 のままにする（T6 でまとめて上げる）。

## T2 オンライン会議の音声（PC で再生中の音声を録る）（1〜2 日）

目的: Zoom / Teams / Meet の相手の声をボットなしで取る。`docs/realtime-meeting-feasibility-2026-07.md` §1-1 の方式。

1. 録音パネルにトグル「PC で再生中の音声も録る（オンライン会議用）」を追加。デフォルト OFF。localStorage に保存。
2. Electron（`desktop/main.js`）: `session.setDisplayMediaRequestHandler` で `desktopCapturer.getSources({types:["screen"]})`
   の先頭を `video` に、`audio: "loopback"` を返す（Windows / macOS）。OS の対応可否を `preload.js` 経由で
   レンダラに渡す（`window.localTranscriber.systemAudio = {supported: bool, reason: string}` のような形）。
   macOS は画面収録の許可が要る。`build-macos.sh` の entitlements / Info.plist に必要な記述
   （`NSScreenCaptureUsageDescription` など）を足す。Electron のバージョンと API 名はまず `desktop/node_modules/electron`
   のドキュメントか型定義で確認してから書く。
3. レンダラ（`recorder.js`）: トグル ON のとき `navigator.mediaDevices.getDisplayMedia({audio: true, video: true})` で
   音声トラックだけを取り、映像トラックは即座に止める。マイクと PC 音声を `AudioContext` で 1 本にまとめ
   （`createMediaStreamSource` ×2 → `createMediaStreamDestination`）、その stream を `MediaRecorder` に渡す。
   レベルメーターも合成後の音で測る。取得に失敗したらトグルを戻してマイクだけで続ける（理由をトースト）。
4. ブラウザ版（Electron 外）でも `getDisplayMedia` があれば同じトグルを出す（Chrome は「タブ/画面の音声を共有」で動く）。
5. トレイのツールチップに「PC 音声あり」が分かる表示を足す（任意）。
6. 実機確認は人がやる。README 2 本と `docs/` に対応 OS と制約（macOS は画面収録の許可、Bluetooth ヘッドセットの注意）を書く。

## T3 話者分離（試験的）（1〜2 日）

方針: 追加の extra `diarize` に `sherpa-onnx`（CPU・トークン不要・MIT 系）を使う。pyannote 本体（torch・Hugging Face の
利用規約同意が必要）は使わない。

1. `pyproject.toml` に `diarize = ["sherpa-onnx>=1.10,<2"]`（実在する版を確認して書く）。
2. `app/diarizer.py`: 初回に sherpa-onnx の公式リリースからモデル 2 つ（pyannote segmentation-3.0 の ONNX と
   3D-Speaker の話者埋め込み ONNX）を `model_dir/diarization/` へダウンロード（URL は
   https://github.com/k2-fsa/sherpa-onnx/releases を**実際に確認**して書く。サイズも記録）。
   音声は `faster_whisper.audio.decode_audio(path, sampling_rate=16000)` で 16kHz mono にする。
   出力は `[{"start", "end", "speaker"}]`。話者数は自動（クラスタリングの閾値）。
3. `app/jobs.py`: options に `diarize: bool`。文字起こしの後に実行し、各 segment に `speaker`
   （「話者1」「話者2」…。重なりが最大の話者）を付ける。進捗表示は `finalizing` の前に「話者を分けています」。
4. `app/exporters.py`: TXT / SRT / VTT は話者が変わる行の先頭に `話者1: `、JSON には `speaker` フィールド。
   UI の結果表示にも話者ラベル。
5. 機能の出し方: `GET /api/config` に `diarize: {"available": bool, "ready": bool, "reason": str}`。
   extra が無い・メモリ 8GB 未満のときは `available: false` で UI に出さない。チェックボックス
   「話者を分ける（試験的・時間がかかります）」。モデルのダウンロードは `/api/setup` と同じ進捗の出し方で。
6. テスト: 偽の diarizer（固定の区間を返す）で、segment への割り当てと書き出しの形を固定する。
7. ビルド: `desktop/backend.spec` で sherpa-onnx の動的ライブラリを集める（`collect_dynamic_libs`）。
   `build-windows.cmd` / `build-macos.sh` の pip install に `diarize` を足す。
   PyInstaller で動かない場合は、ビルド同梱をやめて「`pip install local-transcriber[diarize]` のソース実行のみ」に
   範囲を狭め、その旨を docs に書く（**挙動を壊すより範囲を狭める**）。

## T4 Linux ビルド（半日）

1. `build-linux.sh`（`build-macos.sh` に倣う）: venv → `pip install -e ".[desktop,summary,diarize]"`
   （llama-cpp-python は `--extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cpu`）→
   `vendor/modelshelf`（`modelshelf-linux-x64` を取得して実行権限）→ PyInstaller → `electron-packager --platform=linux --arch=x64`
   → `dist/LocalTranscriber-<version>-linux-x64.tar.gz`。`START_HERE_LINUX.txt` を同梱（起動方法・トレイには
   `libayatana-appindicator3` が要ること）。
2. `.github/workflows/build-linux.yml`（`ubuntu-22.04`、`workflow_dispatch` と `v*` タグ）。artifact 名 `LocalTranscriber-linux-x64`。
3. `desktop/main.js` で Linux 固有の問題（トレイが無い環境ではウィンドウを閉じたら終了する等）に対応。
4. README 2 本に Linux の節を足す。

## T5 Microsoft Store 用 MSIX を CI で作る（半日）

1. `.github/workflows/build-windows.yml` に `package-msix.cmd` の実行と artifact `LocalTranscriber-msix` の
   アップロードを足す（Windows SDK の `makeappx` または `@microsoft/winappcli`。runner に入っているものを使う）。
   署名は Store 側で行うので CI では未署名でよい。
2. `STORE_SUBMISSION.md` を現状に合わせて更新: 機能一覧（0.7.0 の新機能）、バージョン、
   「人がやること」のチェックリスト（Partner Center の本人確認、価格設定、スクリーンショット、申請）。
   Store 版の商品名と価格方針は変えない。

## T6 リリース準備（Claude が確認してタグを打つ）

1. バージョンを 0.7.0 に: `pyproject.toml`、`app/main.py`、`desktop/package.json`、`build-windows.cmd`、
   `build-macos.sh`（あれば）、`build-linux.sh`、`STORE_SUBMISSION.md`。
2. `docs/RELEASE-0.7.0.md`（日本語・社内向け。手順と確認項目）と `docs/release-notes-0.7.0-gh.md`
   （GitHub Release 用。日本語＋英語。0.6.0 のファイルの形に倣う）。
3. README 2 本の機能一覧・表・対応 OS を 0.7.0 の内容に更新。`docs/review-fixes-2026-10-21.md` の内容も
   リリースノートに含める。

## T7 koiyal.com の更新（別リポジトリ `/home/zenkutsu/koiyal-website`。Claude が公開）

- 製品ページ（`src/content.ts` と `src/index.tsx` の local-transcriber の節）: 0.7.0 のダウンロード（3 OS・サイズ）、
  新機能、比較表（Notta / Otter / MacWhisper / Vibe / Meetily。`docs/realtime-meeting-feasibility-2026-07.md` §2 の出典つき）、
  FAQ に「完全ローカル」「オフライン」「無料」「オンライン会議」「話者分離」「Linux」の語を入れる。
- お知らせ記事 `src/posts/2026-10-xx-local-transcriber-0-7-0.md`（0.6.0 の記事に倣う）。

## 進捗

| タスク | 状態 | 残したこと・人がやること |
|---|---|---|
| T1 | 実装完了（2026-10-21） | 繰り返し抑制、32GB以上の Turbo 選択、導入済み Medium の維持と更新候補、用語集（保存・両API・500文字制限）、新版確認（5秒・24時間キャッシュ・無効化）、日英UI・トレイ・READMEを実装。バージョンは0.6.0を維持。pytest 107件、変更JSの node --check、偽通信での通知表示・トレイ問い合わせ間隔を確認済み。安全側に限定し、正式な数値3桁タグと本リポジトリのリリースURL以外は通知しない。通信の繰り返しを避けるため失敗も24時間キャッシュする。未実施: 実モデルの速度・精度評価とWindows/macOSの実機操作。人が録音と用語集の保存、Turboへの更新、通知リンクとトレイ表示を確認する。 |
| T2 | 未着手 | |
| T3 | 未着手 | |
| T4 | 未着手 | |
| T5 | 未着手 | |
| T6 | 未着手 | |
| T7 | 未着手 | |

T1 の確認元: インストール済み `faster_whisper.utils._MODELS` と `WhisperModel.transcribe`、
Electron の `electron.d.ts`、[Turbo の配布ファイル](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/tree/main)、
[GitHub の最新リリース API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)。
Turbo のダウンロード対象5ファイルの合計は 1,621,665,983 bytes（2026-10-21 確認）。
