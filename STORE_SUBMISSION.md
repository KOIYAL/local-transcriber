# Microsoft Store 申請メモ

## 対象バージョンと商品名

アプリ内バージョンは **0.7.0** です。申請用のビルドは、T6 のコミットから作り直します。
リリース前の手順は [0.7.0 リリース手順](docs/RELEASE-0.7.0.md) を参照してください。
この文書の機能説明は T1〜T4 の実装を反映していますが、Windows の実機確認と
Store 審査はまだ完了していません。

商品名は変更しません。

**文字起こし - 買い切りのみのサブスクなし**

価格方針も維持します。有料の買い切りで、サブスクリプションとアプリ内課金はありません。
Partner Center で価格と販売地域を設定し、Subscription / Durable / Consumable add-on は追加しません。
無料試用も今回の変更では追加しません。

## 0.7.0 で追加する説明

- Windows で、PC で再生中の音声とマイクを一緒に録音できます。オンライン会議用の
  設定はデフォルト OFF です。PC 音声を取得できなければ、理由を表示してマイク録音を続けます。
- 社名・人名・製品名を用語集として保存し、文字起こしの参考にできます。最大500文字です。
- 話者分離は試験的な任意機能です。対応する依存と8GiB以上のメモリが必要で、
  メモリを確認できない場合も非表示です。初回は専用モデルの準備が必要です。
  分離できなかった場合は通常の文字起こしを残します。名前や本人の特定は行いません。
- 32GiB以上のメモリでは、新規セットアップ時に Turbo を自動選択します。
  すでに準備したモデルは勝手に変更せず、更新候補を表示します。
- GitHub で新版を確認し、画面とトレイに通知します。`LT_UPDATE_CHECK=off` で停止できます。
  この通知は GitHub Release へのリンクであり、Store の更新機能ではありません。

ローカル要約は既存機能として掲載します。初回に要約モデルの準備が必要です。
対応しない環境では利用できません。Linux のビルド追加は別の配布経路の変更で、
Windows 向け Store 商品の対応 OS には含めません。

## Store 掲載文（日本語）

### 商品名

文字起こし - 買い切りのみのサブスクなし

### 短い説明

音声・動画や会議の録音をPC内で文字起こし。買い切りで、サブスクリプションやAPIキーは不要です。

### 説明

「文字起こし - 買い切りのみのサブスクなし」は、音声・動画ファイルや
会議の録音をWindows PC上で文字に変換するアプリです。

ファイルを選ぶか、アプリ内で録音を開始します。PCのメモリに適したAIモデルを
準備し、音声の言語を検出して文字起こしします。アカウント登録やAPIキーは不要です。
オンライン会議では「PCで再生中の音声も録る」を選ぶと、マイクと相手の音声を
一緒に録音できます。利用できる音声はPCや会議アプリの設定によって異なります。

社名・人名・製品名を用語集に登録できます。対応環境では、話者を分ける試験的な機能や
ローカルAIによる要約も利用できます。認識・話者分離・要約の結果には誤りが含まれる
場合があるため、必要に応じて元の音声と確認してください。

結果はタイムスタンプ付きで表示し、全文コピーとTXT、SRT、VTT、JSONの書き出しに
対応します。要約はSUMMARY.TXTとして保存できます。

音声・動画・用語集・文字起こし・要約を外部へ送信しません。各機能の初回準備や
利用者が選んだモデルの更新では、モデルをダウンロードします。モデル準備後の
文字起こし・話者分離・要約はPC内で処理でき、オフラインでも利用できます。
新版の確認だけはGitHub APIへ通信し、本文や音声を含みません。
環境変数 `LT_UPDATE_CHECK=off` で新版確認の通信を停止できます。

本製品は買い切りです。月額・年額サブスクリプション、アプリ内課金、
外部APIの利用料金はありません。

### 機能一覧

- 音声・動画ファイルのドラッグ＆ドロップとファイル選択
- アプリ内でのマイク録音と、停止後の文字起こし
- PCで再生中の音声とマイクの同時録音（任意）
- 録音中は数秒ごとにPC内へ保存
- トレイから録音の開始・停止・一時停止
- トレイアイコンで待機・録音・一時停止・処理中の状態を表示
- 社名・人名・製品名の用語集を保存（最大500文字）
- PCのメモリに応じたモデル選択と初回ダウンロード
- 音声言語の自動検出と無音区間の除外
- 話者ラベルの表示と書き出し（試験的・対応環境のみ・追加モデルが必要）
- ローカルAIによる要約とSUMMARY.TXTの保存（任意・追加モデルが必要）
- タイムスタンプ付きの結果表示と全文コピー
- TXT / SRT / VTT / JSON形式で保存
- 書き出しの保存先フォルダを指定
- 各モデルの準備後はオフラインで処理
- 新版のお知らせ（停止可能）
- 日本語・英語の画面表示
- 買い切り、ログイン・APIキー・サブスクリプション不要

### 検索語

文字起こし, 音声認識, 会議録音, ローカル, 字幕, SRT, VTT, Whisper

### サポートとプライバシー

- Website: https://koiyal.com/
- Contact form: https://repoan.com/f/37a22b84-4251-4e04-a363-27d650428684
- X: https://x.com/KOIYAL_AI
- Privacy policy: https://koiyal.com/footer/privacy

お問い合わせはウェブサイトのお問い合わせフォーム、またはXのDMで受け付けています。

## Store listing (English)

### Description

Transcribe audio, video, and meeting recordings privately on your Windows PC.
Select or drop a file, or record directly in the app. For online meetings,
optionally combine microphone audio with sound playing on your PC. Audio
capture depends on your computer and meeting app settings.

The app selects a transcription model for your computer's memory and detects
the spoken language automatically. Save company, person, and product names
in a glossary of up to 500 characters. Experimental speaker labels are
available on supported computers with at least 8 GiB of memory and require
additional model setup. Optional local AI summaries also require model setup.
Review the results against the recording when accuracy matters.

View timestamped transcripts, copy the complete text, or export TXT, SRT,
VTT, and JSON files. Save summaries as SUMMARY.TXT.

Audio, video, glossary entries, transcripts, and summaries are not sent to an
external service. Internet access is used to download models during setup
or when you choose a model upgrade. Once the relevant models are ready,
transcription, speaker separation, and summaries can run offline. A separate
GitHub API request checks for new releases without sending audio or text.
Set the environment variable LT_UPDATE_CHECK=off to disable this check.

This is a one-time purchase. There are no monthly or annual subscriptions,
in-app purchases, account requirements, API keys, or external API usage fees.

### Product features

- Local audio and video transcription with drag-and-drop or file selection
- In-app microphone recording, with optional PC audio for online meetings
- Recording saved to disk every few seconds
- Start, pause, and stop recording from the system tray
- Tray icons show recording and processing states
- Saved glossary of names and technical terms, up to 500 characters
- Automatic model selection based on computer memory
- Automatic language detection and silence filtering
- Experimental speaker labels on supported computers after model setup
- Optional local AI summaries and SUMMARY.TXT export after model setup
- Timestamped results, full-text copy, and TXT / SRT / VTT / JSON export
- Choose an export folder
- Offline processing after the relevant model downloads
- Optional new-release notifications
- Japanese and English interface
- One-time purchase with no subscriptions or in-app purchases

## MSIX の作成と CI 設定

### Partner Center の識別情報

`Partner Center > Product management > Product identity` から次の値をそのまま転記します。
開発用の仮の識別情報では Store 向けパッケージを作りません。

| 設定名 | 転記元・内容 |
|---|---|
| `STORE_IDENTITY_NAME` | `Package/Identity/Name` |
| `STORE_PUBLISHER` | `Package/Identity/Publisher` |
| `STORE_PACKAGE_VERSION` | Store 用の4桁の番号。既存の提出済みパッケージより大きい値を選ぶ |

`Package/Properties/PublisherDisplayName` は現在 `株式会社KOIYAL` を使います。
Partner Center の値と一致することを確認してください。

アプリの 0.7.0 と Store のパッケージ番号は別に管理します。
ローカルスクリプトのデフォルトは既存の **1.0.2.0** を維持しますが、CI では
`STORE_PACKAGE_VERSION` の明示設定を必須にします。以下の **1.0.3.0** は例であり、
最新の提出履歴を確認してから使ってください。アプリのバージョンを自動変換して
0.7.0.0にすると、既存パッケージより小さくなるため使用しません。
末尾は0、先頭は1〜65535、中央2つは0〜65535の整数で指定します。

### GitHub Actions

1. リポジトリの `Settings > Secrets and variables > Actions > Variables` に上表の3項目を設定します。
   これらはパッケージに含まれる公開情報です。証明書・秘密鍵・パスワードは登録不要です。
2. T6 のバージョン更新後のコミットで `Build Windows app` を手動実行します。
   `v*` タグでも起動しますが、タグ作成と公開は別の担当が行います。
3. `LocalTranscriber-win-x64` にポータブルZIP、`LocalTranscriber-msix` に
   未署名の `KOIYAL-Transcriber-Store.msix` が保存されます。
4. 3項目のいずれかが空ならMSIXだけをスキップし、Actionsの概要に未設定の項目名を表示します。
   設定後に再実行してください。値を設定した後の番号形式エラーやパッケージ作成失敗は
   ジョブ失敗となり、成功したようには扱いません。ポータブルZIPはその前に保存されます。

CI は `npm ci` で `desktop/package-lock.json` の winapp CLI（確認時点では0.3.2）を使い、
`package-msix.cmd` を実行します。`SIGNING_CERT` は空に固定します。
Store へのアップロード・申請・GitHub Release への公開は行いません。

### Windows で手動作成

先に `build-windows.cmd` を実行します。タイル画像は `assets/msix/` を使い、
winapp CLI が作る画像を製品用の画像に差し替えます。

```powershell
$env:STORE_IDENTITY_NAME = "Partner Center の Package/Identity/Name"
$env:STORE_PUBLISHER = "Partner Center の Package/Identity/Publisher"
$env:STORE_PACKAGE_VERSION = "1.0.3.0" # Choose a version higher than previous submissions.
$env:SIGNING_CERT = ""
.\package-msix.cmd
```

出力は `dist\KOIYAL-Transcriber-Store.msix` です。古い `LocalTranscriber.msix` は
開発用の識別情報を含むため提出しません。Store は提出時に署名するためCIでの署名は不要です。
未署名MSIXをそのまま一般配布用のインストーラーには使いません。
実機確認では別途テスト用証明書で署名したコピーや、Partner Center のテスト配布を使います。

## runFullTrust の申請理由（日本語）

本アプリはElectronと同梱のPython/faster-whisperバックエンドで構成された
Win32デスクトップアプリです。ユーザーが選択・録音した音声・動画を読み込み、
同梱バックエンドを子プロセスとして起動し、端末上で文字起こし・話者分離・要約を
行うためにrunFullTrustが必要です。PC音声の録音は利用者が選んだ場合に行います。

バックエンドはランダムに選択された127.0.0.1のポートだけで待ち受けます。
管理者権限の要求、システム設定の変更、他アプリの操作は行いません。
モデルの初回準備や利用者が選んだ更新ではダウンロードします。
新版確認ではGitHub APIへ本文や音声を含まないリクエストを送り、結果を失敗時も含めて
24時間保存します。`LT_UPDATE_CHECK=off`（`0` / `false` / `no` も可）で停止できます。
音声・用語集・文字起こし・要約は外部に送信しません。

## runFullTrust justification (English)

This packaged Win32 application uses Electron and a bundled Python backend.
The runFullTrust capability is required to launch the backend and process
user-selected or recorded audio and video locally for transcription, speaker
separation, and summaries. PC audio capture is enabled only when the user
chooses it. The backend listens only on a randomly selected 127.0.0.1 port.
The app does not request administrator privileges, change system settings,
or control other applications.

Internet access downloads models during setup or a user-selected upgrade.
A separate GitHub API request checks for releases without including user
content. Results, including failures, are cached for 24 hours. This check
can be disabled with LT_UPDATE_CHECK=off (also 0, false, or no).
Audio, glossary entries, transcripts, and summaries stay on the computer.

## 審査担当者向けの確認手順

アカウント登録・ログイン・APIキーは不要です。初回はインターネットに接続して
文字起こしモデルの準備完了を待ち、音声・動画を選択して「文字起こしを開始」を押します。
結果のコピーと各形式の保存を確認できます。マイク録音は許可を与えて開始し、
停止すると文字起こしへ進みます。PC音声は録音パネルで任意に有効にします。
話者分離と要約はそれぞれモデルの準備が必要です。非対応環境では機能が表示されません。

処理成功時は元音声の一時コピーを削除します。失敗・中断時は録音を失わないよう残します。
結果と要約はPC内に保存します。元のファイルを外部サービスへ送信しません。

### Certification notes (English)

No sign-in or API key is required. Connect to the internet for initial model
setup, then select an audio or video file and click Start transcription.
Check copying and export of the completed transcript. Grant microphone
permission for recording; stopping a recording starts transcription. PC audio
capture is optional. Speaker separation and summaries need their own model
setup and are hidden on unsupported systems.

Temporary source copies are deleted after successful transcription. Failed
or interrupted recordings are retained to avoid losing the audio. Transcripts
and summaries remain on the PC. Support: https://koiyal.com/

## 人がやること

- [ ] Partner Center の本人確認・会社情報確認を完了する。
- [ ] 既存商品の予約名と識別情報、発行者の表示名を確認する。商品名を変更しない。
- [ ] 価格・販売地域を設定する。買い切り方針を維持し、サブスクリプションとアプリ内課金を追加しない。
- [ ] 提出履歴から次の Store パッケージ番号を決め、Actions の3変数を設定する。
- [x] T6 でアプリの0.7.0表記を統一する（Store用の4桁の番号は別管理）。
- [ ] T6 のコミットでWindows CIを実行し、0.7.0の申請用ビルドを作り直す。
- [ ] MSIXの生成、識別情報・番号・x64構成・タイル画像・同梱バックエンドを確認する。
- [ ] Windows の実機でインストール、起動、終了、既存パッケージからの更新、保存先を確認する。
- [ ] マイク・PC音声の録音と権限拒否時の挙動、用語集、話者分離、要約、書き出しを確認する。
  手順は [PC音声](docs/system-audio-2026-10-21.md) と [話者分離](docs/diarization-2026-10-21.md) を参照する。
- [ ] モデル準備後のオフライン処理と `LT_UPDATE_CHECK=off` を確認する。
  Store利用者にGitHub版の通知が出ることも確認し、掲載文と審査メモに説明する。
- [ ] Windows App Certification Kit で確認し、runFullTrust の申請理由とプライバシーポリシーを見直す。
- [ ] 年齢区分の質問票を入力する。通常のユーティリティとして実際の機能に沿って回答する。
- [ ] 0.7.0 の日本語・英語スクリーンショットを撮り直す。`store-assets/screenshots/ja-JP` と
  `store-assets/screenshots/en-US` の既存画像をそのまま最新版として扱わない。
- [ ] 任意機能が配布ビルドで動くことを確認してから掲載文を転記する。同梱できない機能は説明から外す。
- [ ] `LocalTranscriber-msix` のMSIXをPartner Centerへアップロードし、掲載内容・価格・画像を確認して申請する。
  この作業ではアップロード・申請・公開は実施していない。

## 確認した公式資料

- [winapp CLI v0.3.2 リリース](https://github.com/microsoft/winappCli/releases/tag/v0.3.2)
- [v0.3.2 のコマンド仕様](https://github.com/microsoft/winappCli/blob/v0.3.2/docs/usage.md)
- [package コマンドの実装](https://github.com/microsoft/winappCli/blob/v0.3.2/src/winapp-CLI/WinApp.Cli/Commands/PackageCommand.cs)
- [Microsoft Store のパッケージ要件と番号](https://learn.microsoft.com/en-us/windows/apps/publish/publish-your-app/msix/app-package-requirements)
- [MSIX の署名と Store 提出](https://learn.microsoft.com/en-us/windows/msix/package/sign-msix-package-guide)
