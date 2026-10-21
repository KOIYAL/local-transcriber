# 話者分離（試験的）の実装と確認

## 使い方と対象環境

- デフォルトは OFF。画面の「話者を分ける（試験的・時間がかかります）」を選ぶ。
  ファイルとアプリ内録音に共通で使い、再起動・ページ再読み込みでは OFF に戻る。
- `sherpa-onnx` が読み込めて、メモリが 8 GiB 以上の環境だけに表示する。
  メモリを確認できない場合や動的ライブラリが不足する場合も隠す。
- ソース実行では `.venv/bin/pip install -e ".[diarize]"` で追加し、アプリを再起動する。
  公開済みパッケージへ追加する形式は `pip install 'local-transcriber[diarize]'`。
  このコミットはバージョンを 0.6.0 のままにしており、今回の機能の配布は T6 以降。
- 最初に選んだときだけ、公式 GitHub Release からモデルを約 46.6 MB 取得する。
  保存先は `WHISPER_MODEL_DIR/diarization/`。環境変数未指定時は `data/models/diarization/`。
  準備中は割合を表示し、チェックは OFF のままになる。この間に始めた処理には話者ラベルを付けない。
  準備成功後にチェックが入り、以降の処理に使う。失敗時は通常の文字起こしと再試行を選べる。
- モデルがあれば起動時にローカルでサイズ・SHA-256 を確認する。推論時の外部通信はない。
  音声、用語集、文字起こし、要約は外へ送らない。モデル取得以外の通信については README の新版確認を参照。

## 処理と制限

`faster_whisper.audio.decode_audio(path, sampling_rate=16000)` で 16 kHz mono にし、
sherpa-onnx の CPU 推論を文字起こしの後、書き出しの前に実行する。
`FastClusteringConfig(num_clusters=-1, threshold=0.5)` で話者数を推定する。
pyannote の Python パッケージ、torch、Hugging Face のトークンは使わない。

話者番号は録音ごとの登場順。各文字起こし区間と話者区間の重なりを話者ごとに合計し、
最大の話者を割り当てる。同率なら先に登場した話者を選ぶ。重ならない区間にはラベルを付けない。
一つの文字起こし区間を細分化しないため、短い交代・同時発話・雑音・似た声では誤ることがある。
人物名の特定や、別の録音との人物対応はしない。会議時間に応じて追加の時間とメモリが必要。

TXT / SRT / VTT は話者が変わる行に `話者1: ` のようなラベルを付ける。
JSON の各区間には `speaker` を加える。結果表示、全文コピー、要約へ渡す本文にも反映する。
ラベルは英語 UI でも `話者1` の形式を使う。

話者分離の推論に失敗した場合は、通常の文字起こしを完了させ、日英の説明を結果欄に表示する。
JSON の `diarization_failed: true` でも判別できる。このときは `KEEP_UPLOADS` に関係なく元音声を
`data/uploads/` に残す。話者分離によって録音が失われないようにするための判断。

## API

- `GET /api/config` の `diarize`: `available`, `ready`, `reason`, `status`, `progress`, `download_bytes`。
  利用不可の理由は `sherpa_onnx_unavailable`, `memory_below_8gb`, `memory_unknown`。
- `GET /api/diarize/setup`: 状況の取得だけ。アクセスしてもダウンロードを開始しない。
- `POST /api/diarize/setup`: 明示的な準備・再試行。バックグラウンド処理で重複開始を防ぐ。
- `POST /api/jobs` と `POST /api/recording/{id}/stop`: 任意の form 値 `diarize`。未指定は false。
  ファイルでは true で未準備なら 409。録音の停止は受け付け、未準備ならジョブ内で通常の文字起こしへ戻す。
  古い画面設定からの停止でも、既存のエラー後の録音破棄処理につながらないようにする。
- ジョブ状態 `diarizing` を追加。処理中の削除・古いジョブの整理の対象から除き、トレイも処理中として扱う。

## 公式情報と実物の確認（2026-10-21）

- [公式リリース一覧](https://github.com/k2-fsa/sherpa-onnx/releases)
- [話者区間モデル](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-segmentation-models)
- [話者埋め込みモデル](https://github.com/k2-fsa/sherpa-onnx/releases/tag/speaker-recongition-models)
- [公式 Python サンプル](https://github.com/k2-fsa/sherpa-onnx/blob/master/python-api-examples/offline-speaker-diarization.py)
- [PyPI の sherpa-onnx](https://pypi.org/project/sherpa-onnx/1.13.8/)

実在を確認してインストールした 1.13.8 のコンストラクタ・`process`・コールバック・`sample_rate` と、
実際のモデルで API を確認した。未確認の旧 API を対象に含めないため extra は `sherpa-onnx>=1.13.8,<2` に限定。
`collect_dynamic_libs("sherpa_onnx")` は、分割された core パッケージが同じディレクトリへ置くライブラリも集める。
Windows / macOS のビルド手順に `diarize` extra を追加した。

| 配布ファイル | ダウンロードサイズ | 保存するモデルのサイズ |
|---|---:|---:|
| sherpa-onnx-pyannote-segmentation-3-0.tar.bz2 | 6,958,444 bytes | model.onnx: 5,992,913 bytes |
| 3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx | 39,593,761 bytes | 39,593,761 bytes |

取得した実ファイルから計算した SHA-256 は `app/diarizer.py` に固定した。
サイズ・ハッシュが変わった配布物は準備失敗として扱う。アーカイブは指定した通常ファイル一つだけを取り出し、
リンクや任意のパスを展開しない。完了前のファイルを ready にせず、失敗した部分ファイルは残さない。
モデルは再配布せず、利用者の選択後に公式配布元から取得する。

## 実施済みの確認

- pytest 129 件。新しい連携は偽ダウンローダー・デコーダー・推論エンジンで検証し、テストではネットワーク・実モデル・外部バイナリを使っていない。
- Node テスト 21 件。未対応環境の非表示、起動時のダウンロードなし、準備・失敗・日英表示、ファイルと録音への設定伝達、結果ラベル、既存の PC 音声機能を確認。
- 変更した JS の `node --check`、Mac ビルドスクリプトの `bash -n`。
- テストとは別に、Linux / Python 3.12 のソース実行で公式モデルを読み込み、5 秒の人工無音を処理して正常終了を確認。
- Linux で `desktop/backend.spec` を PyInstaller 6.22.3 でビルドし、生成バックエンドを起動。
  `/api/config` の `diarize.available: true` を確認。ビルド成果物と検証用モデルは `/tmp/` のみ。

## 人が確認すること

1. Windows / macOS でビルドし、起動・モデル準備・再起動後のオフライン推論を確認する。
   この環境では両 OS の動作を未確認。同梱時に問題があれば配布前にソース実行だけへ限定する。
2. 日本語・英語の複数話者の会議音声で、人物交代、同時発話、長時間録音の精度・所要時間・メモリを確認する。
3. ファイルとアプリ内録音の両方で、OFF 時の従来動作、ON 時の話者表示、全文コピー、4 形式の出力、要約を確認する。
4. 初回のネットワーク切断からの再試行、準備中に通常の文字起こしを開始する操作、ページ再読み込みを確認する。
5. 推論に失敗した場合の説明と元音声の保存先、話者分離中のトレイ表示・終了確認を確認する。
