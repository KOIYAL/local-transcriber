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
| T2 | 実装完了（2026-10-21） | デフォルトOFF・設定保存の日英トグル、Electronのloopbackとpreload対応判定、ブラウザの共有、マイクとの合成・合成後メーター、映像の即時停止、失敗時と共有終了時のマイク継続、停止・破棄・開始失敗時の解放、Macの権限説明、README2本と実機確認文書を追加。pytest 107件、偽APIによるNodeテスト16件、変更JSの node --check、bash構文・plist検証を実施。安全側に限定し、Macは公式に確認したCoreAudio Tap経路を使う14.2以降のパッケージ版だけを対象にする。古いMac・権限説明を保証できないMacの開発起動・LinuxのElectronでは隠す。任意のトレイツールチップは未追加で、録音パネルに「PC 音声あり」を表示する。未実施: Windows/macOSの実機録音、Macビルドと権限ダイアログ、ブラウザの実共有。人が docs/system-audio-2026-10-21.md に沿って相手と自分の音声、共有拒否・途中終了、トレイ操作、Bluetoothを確認する。 |
| T3 | 実装完了（2026-10-21） | 任意のdiarize extra、CPU話者分離、公式モデル2つの明示的な初回取得と進捗・再試行・サイズ/SHA-256検証、両APIの設定、最大重なりによる話者割り当て、日英UI、TXT/SRT/VTT/JSON・全文コピー・要約への反映、処理中のトレイ・削除防止、ビルド設定、README2本と確認文書を追加。デフォルトOFF。未導入・8GiB未満・メモリ確認不能なら隠す。安全側に限定し、実物でAPIを確認したsherpa-onnx 1.13.8以上を対象にし、重なりのない文には話者を付けない。準備中に開始した処理にはラベルを付けず、その旨を表示。録音停止は未準備でも受け付け、分離失敗時は通常の文字起こしと元音声を保持して説明を表示する。pytest 129件、偽APIによるNodeテスト21件、変更JSの node --check、bash構文確認済み。LinuxでPyInstallerバックエンドのビルド・起動・同梱ライブラリ読み込みを確認。テスト外で実モデルによる人工無音の処理も確認。未実施: Windows/macOSビルドの実機動作、会議音声の精度・速度・長時間のメモリ評価。人が docs/diarization-2026-10-21.md に沿って両OSの準備・オフライン推論・録音・出力を確認する。同梱に問題があれば配布前にソース実行のみへ限定する。バージョンは0.6.0を維持。 |
| T4 | 実装完了（2026-10-21） | Linux x64 のビルドスクリプト、Ubuntu 22.04 の手動実行・タグ対応CI、日英の同梱案内とREADME、実機確認文書を追加。バージョンは0.6.0を維持。Linuxはトレイの表示可否を確実に判断できないため、常にウィンドウを閉じると終了する範囲に限定。トレイ作成失敗でも起動を続け、録音中・一時停止中の終了確認を維持する。公式modelshelf v0.2.0の実ファイルはglibc 2.39が必要でUbuntu 22.04では動かないため、URL・SHA-256を固定して取得し、実行できない環境では同梱を省いて通常は要約UIを隠す。pytest 129件、偽APIによるNodeテスト27件、変更JSの node --check、bash構文・YAML確認済み。Ubuntu 24.04でtar.gz（285,303,324 bytes）の実生成、内容・実行権限、同梱バックエンドの起動・終了、要約と話者分離の依存読み込み、新版確認OFFを確認。modelshelfを省いたバックエンドも別途ビルドし、要約が利用不可・話者分離が利用可能になることを確認。未実施: GitHub Actionsの実行、Ubuntu 22.04での起動、実機GUI・マイク録音・実音声の推論。人が docs/linux-build-2026-10-21.md に沿ってGNOME/KDE、X11/Wayland、トレイあり・なし、終了確認、書き出し、オフライン動作を確認する。公開はしていない。 |
| T5 | 実装完了（2026-10-21） | Windows CIに未署名MSIX作成とLocalTranscriber-msix artifactを追加。公式v0.3.2の実装でwinappのAPIを確認し、npm ciでlockfileの依存を使用、実行ファイルを明示、必要なツールと識別情報を事前確認。Store番号の形式検証とテスト、README.ja.mdのCI案内、日英の掲載文・通信説明・申請チェックリストを更新。商品名と買い切り方針、アプリの0.6.0表記、ローカルのStore番号デフォルト1.0.2.0は維持。安全側に限定し、CIはSTORE_IDENTITY_NAME・STORE_PUBLISHER・STORE_PACKAGE_VERSIONのいずれかが未設定ならMSIXだけをスキップして概要に理由を表示する。仮の識別情報や提出履歴未確認の番号を使わず、ポータブルZIPの作成を維持するため。設定済みの作成失敗はジョブ失敗とする。pytest全142件、actionlint・YAML検証、npm ciのlockfile確認が成功。JS変更なし。未実施: Windows CIの実行、MSIX実生成・インストール・既存パッケージからの更新・認定キット、Store申請・公開。人がSTORE_SUBMISSION.mdに沿ってPartner Centerの本人確認、価格設定、識別情報と最新提出番号の確認・CI変数設定、T6後の再ビルド、実機の録音・話者分離・要約・オフライン動作、日英スクリーンショットと掲載文の確認、申請を行う。 |
| T6 | 実装完了（2026-10-21） | アプリ・Pythonパッケージ・Electron・lockfile・Windows ZIPの番号を0.7.0に統一。macOS/Linuxは既存のpackage.json参照を維持し、導入済みElectron Packagerで3 OSとも0.7.0になることを確認。社内リリース手順と日英リリースノートを追加し、レビュー修正12件・追加修正・後続レビュー4件を反映。README2本の機能・OS表・メモリ表・設定保存・各区間への用語集反映・CUDA説明・失敗時の音声保持、Store申請メモを更新。pytest全150件、Node全33件、全JSのnode --check、bash構文、git diff --check、番号の一致・依存lock維持・文書リンクを確認済み。安全側に限定し、Linuxはテスト配布対象、話者分離は試験的と明記。未検証の配布物やサイズを公開済みとして書かず、DMGの既存名とStoreの別管理番号を維持。未実施: 0.7.0の3 OSビルド・CI実行・実機確認・MSIX生成・署名公証・スクリーンショット撮り直し。人がdocs/RELEASE-0.7.0.mdに沿ってPC音声、配布物での話者分離spawnと録音中の応答、長時間音声、設定復元、既存環境からの更新、オフライン動作を確認する。Claudeが差分を確認し、承認後にタグ・push・Release公開、Store申請を行う。T7と公開は実施していない。 |
| T7 | 未着手 | |
| レビュー反映 | 実装完了（2026-10-21、c903bf0） | 指摘4件を修正。PC音声のsecurityOriginをURL.originで正規化し、末尾スラッシュあり・なしと拒否条件を確認。話者分離はmultiprocessingのspawnで子プロセスへ移し、進捗と結果をPipeで受け取る。例外・異常終了・時間切れでは子プロセスを終了・回収し、文字起こし・出力・元音声を保持する。長い録音を短時間で打ち切らないよう推論の制限時間は1時間とした。用語集・マイク・表示言語・PC音声トグルはpreload/IPCから既存のsettings.jsonへ保存し、ブラウザはlocalStorageを維持。初期表示と録音開始時のユーザー操作の扱いを変えないため、小さな同期APIに限定し、送信元・4項目のキー・値を検証する。導入済みfaster-whisper 1.2.1のgenerate_segmentsとget_promptを確認し、用語集を各窓のhotwordsへ変更。最初の窓で重複するためinitial_promptは併用せず、APIの既存options名と繰り返し抑制は維持。pytest全150件、Node全33件、変更JSのnode --check、git diff --checkが成功。偽ワーカーの実際のspawn・失敗・異常終了・時間切れ・再試行、ジョブの文字起こし成功、設定の新プロセス・別ポートでの復元、偽モデルで実ライブラリの90秒・3窓すべてへの用語集反映を確認。未実施: Windows/macOSの実機録音と再起動後の設定復元、PyInstaller配布物でのspawn、実モデルの速度・精度。人が両OSのPC音声取得、設定保存、話者分離中のAPI応答・録音チャンク保存、長時間音声を確認する。公開はしていない。 |

T1 の確認元: インストール済み `faster_whisper.utils._MODELS` と `WhisperModel.transcribe`、
Electron の `electron.d.ts`、[Turbo の配布ファイル](https://huggingface.co/dropbox-dash/faster-whisper-large-v3-turbo/tree/main)、
[GitHub の最新リリース API](https://docs.github.com/en/rest/releases/releases#get-the-latest-release)。
Turbo のダウンロード対象5ファイルの合計は 1,621,665,983 bytes（2026-10-21 確認）。
