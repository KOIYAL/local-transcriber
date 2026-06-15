# Local Transcriber

音声・動画ファイルを `faster-whisper` で文字起こしするWindowsアプリです。
推論はPC内で実行され、外部の文字起こしAPIやAPIキーは必要ありません。

## 主な機能

- 音声・動画ファイルのドラッグ＆ドロップ
- Windows・ブラウザの言語に応じた日本語 / English表示と手動切替
- PCのメモリに応じたWhisperモデルの自動選択と初回ダウンロード
- 言語の自動検出
- 無音区間の自動除外
- 処理状況とタイムスタンプ付きセグメントの表示
- TXT / SRT / VTT / JSON形式でダウンロード
- 初回セットアップ後のオフライン利用

## 一般ユーザー向けWindowsアプリ

ポータブル版は次のフォルダーに生成されます。

```text
dist\electron\LocalTranscriber-win32-x64
```

フォルダー全体をZIPで配布し、利用者は展開後に
`LocalTranscriber.exe` をダブルクリックします。Python、Node.js、ffmpegの
インストールは不要です。

初回起動時のみ、PCのメモリに合わせたモデルを自動でダウンロードします。
準備完了後は、ファイルを選んで「文字起こしを開始」を押すだけです。
日本語環境では日本語、その他の環境では英語を初期表示します。画面右上から
いつでも切り替えられ、選択内容は次回起動時にも維持されます。

### English quick start

1. Extract the complete ZIP archive.
2. Double-click `LocalTranscriber.exe`.
3. On the first launch, wait while the app downloads a model selected for the PC.
4. Select or drop an audio/video file, then click **Start transcription**.

Python, Node.js, an API key, and a separate ffmpeg installation are not required.
After the first setup, transcription can run offline.

モデルの自動選択基準:

| PCのメモリ | 使用モデル |
| --- | --- |
| 8GB未満 | Tiny |
| 8GB以上 | Base |
| 16GB以上 | Small |
| 32GB以上 | Medium |

モデルはユーザーごとのアプリデータ領域に保存されます。アプリを更新しても、
同じモデルを再ダウンロードする必要はありません。

## 必要環境

- Windows 10/11、macOS、Linux
- Python 3.10以上
- 初回のモデル取得にインターネット接続
- 空き容量の目安: Smallで約1GB、Large v3で約3GB以上

`faster-whisper` はPyAV経由で音声を読み込むため、通常はシステムに
`ffmpeg` を別途インストールする必要はありません。

## Web版をWindowsで起動

PowerShellまたはコマンドプロンプトで次を実行します。Windowsの
PowerShell実行ポリシーには影響されません。

```bat
run.cmd
```

初回は `.venv` の作成と依存関係のインストールを行います。起動後、
ブラウザで `http://127.0.0.1:8000` を開いてください。

開発時に自動リロードを有効にする場合:

```bat
run.cmd --reload
```

別のポートを使う場合:

```powershell
$env:PORT = "9000"
.\run.cmd
```

## 手動で起動

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

macOS / Linuxでは仮想環境の有効化だけ読み替えてください。

```bash
source .venv/bin/activate
```

## モデルについて

モデルは初回だけHugging Faceから取得され、以後はローカルから読み込みます。
CUDA対応GPUがある場合は自動的にCUDAを使用します。CUDAランタイムやcuDNNなどが
不足してGPU推論を開始できない場合はCPUへ切り替えます。

完全にローカルのモデルを使う場合は、CTranslate2変換済みの
faster-whisper互換モデルを用意し、環境変数を設定します。

```powershell
$env:WHISPER_LOCAL_MODEL = "C:\models\faster-whisper-small"
.\run.ps1
```

設定後はモデル一覧に `Local` が表示されます。

## 環境変数

`.env.example` に設定例があります。現状は `.env` の自動読み込みを行わないため、
PowerShellやOSの環境変数として設定してください。

| 変数 | 既定値 | 説明 |
| --- | --- | --- |
| `MAX_UPLOAD_MB` | `2048` | 1ファイルの最大サイズ |
| `WHISPER_DEVICE` | `auto` | `auto` / `cpu` / `cuda` |
| `WHISPER_COMPUTE_TYPE` | `auto` | CPUは`int8`、CUDAは`float16`を自動選択 |
| `WHISPER_LOCAL_MODEL` | 空 | ローカルモデルディレクトリ |
| `WHISPER_MODEL_DIR` | `./data/models` | モデルキャッシュ |
| `TRANSCRIBER_DATA_DIR` | `./data` | アップロード・出力の保存先 |
| `KEEP_UPLOADS` | `false` | 処理後も元ファイルを残す |
| `TRANSCRIBER_WORKERS` | `1` | 同時推論数。GPUメモリに注意 |

## データの扱い

- アップロードファイルは `data/uploads` に一時保存します。
- 既定では処理成功・失敗にかかわらず元ファイルを削除します。
- 出力ファイルは `data/outputs/<job-id>` に残ります。
- ジョブ一覧はメモリ上に保持するため、サービス再起動後は画面から過去の出力を
  参照できません。
- インターネットへ公開する認証機能はありません。既定の
  `127.0.0.1` のままローカルで利用してください。

## テスト

```powershell
python -m pip install -e ".[dev]"
python -m pytest
```

## Windowsアプリをビルド

開発マシンにはPython 3.10以上とNode.jsが必要です。

```bat
build-windows.cmd
```

このコマンドは次を実行します。

1. PyInstallerで文字起こしバックエンドをEXE化
2. Electronアプリへバックエンドを同梱
3. `dist\electron\LocalTranscriber-win32-x64` にポータブル版を生成

## MSIXを生成

このプロジェクトはMicrosoftのWindows App Development CLI
（`winapp CLI`）をnpm依存関係として使用します。

Microsoft Store用MSIXの生成には、Partner Centerの
`Product management > Product identity` に表示される値が必要です。

```powershell
$env:STORE_IDENTITY_NAME = "Package/Identity/Nameの値"
$env:STORE_PUBLISHER = "Package/Identity/Publisherの値"
.\package-msix.cmd
```

出力:

```text
dist\KOIYAL-Transcriber-Store.msix
```

署名証明書を使う場合:

```powershell
$env:SIGNING_CERT = "C:\certificates\publisher.pfx"
.\package-msix.cmd
```

署名なしMSIXはMicrosoft Storeへの提出用です。Webサイトなどで直接配布する場合は、
信頼されたコード署名証明書で署名するか、ポータブル版をZIPで配布してください。
Store申請用の入力例と`runFullTrust`の説明文は
`STORE_SUBMISSION.md`を参照してください。

## Macアプリをビルド

Mac版はmacOS上でビルドします。Xcode Command Line Tools、Python 3.10以上、
Node.jsが必要です。

```bash
chmod +x build-macos.sh
./build-macos.sh
```

実行中のMacに合わせて、Apple Siliconでは`arm64`、Intel Macでは`x64`版を
生成します。出力先は次のとおりです。

```text
dist/electron/LocalTranscriber-darwin-<arch>/LocalTranscriber.app
dist/LocalTranscriber-macOS-<arch>.dmg
```

一般配布用の署名済みDMGを作る場合は、Apple Developer Programへ登録し、
Developer ID Application証明書と公証用のキーチェーンプロファイルを用意します。

```bash
xcrun notarytool store-credentials "koiyal-notary"
export MAC_CODESIGN_IDENTITY="Developer ID Application: 株式会社KOIYAL (TEAMID)"
export MAC_NOTARY_PROFILE="koiyal-notary"
./build-macos.sh
```

署名情報を設定しない場合は、動作確認用の未署名DMGを生成します。一般ユーザーへ
配布する版はDeveloper IDで署名し、Appleの公証を完了させてください。

Mac App Store版はApp Sandbox、ファイルアクセス権限、同梱バックエンドの署名に
追加対応が必要です。まずはDeveloper IDで署名・公証したDMGによる配布を推奨します。

## API

- `GET /api/health`: 稼働確認
- `GET /api/config`: アップロード設定と初回準備状態
- `GET /api/setup`: 自動モデル準備の開始・状態取得
- `POST /api/jobs`: ファイルをアップロードしてジョブ作成
- `GET /api/jobs/{job_id}`: 状況と結果を取得
- `GET /api/jobs/{job_id}/download/{txt|srt|vtt|json}`: 結果を取得
- `DELETE /api/jobs/{job_id}`: 完了済みジョブと出力を削除

API仕様は起動後の `http://127.0.0.1:8000/docs` でも確認できます。
