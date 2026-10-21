# Linuxビルドと確認項目（2026-10-21）

T4 は x86_64 Linux 向けの tar.gz を作る。バージョンは T6 まで 0.6.0 のまま。
`build-linux.sh` と `.github/workflows/build-linux.yml` がビルド手順の元のファイル。
CI は Ubuntu 22.04、Python 3.12、Node.js 22 を使う。
ビルドの実行には依存パッケージと配布バイナリのダウンロードが発生する。

## 対応範囲

- Ubuntu 22.04 以降の x86_64 デスクトップを対象にする。新しい OS で作った
  バイナリを古い OS で使えるとは限らない。ARM64、Alpine、画面のない環境は対象外。
- Electron の GTK 3、NSS、ALSA などは OS 側に必要。トレイには
  `libayatana-appindicator3`（Ubuntu: `libayatana-appindicator3-1`）と
  デスクトップの AppIndicator 対応が必要。GNOME の拡張機能などは利用者が用意する。
- Electron 42.4.0 の型定義と [公式 Tray ドキュメント](https://www.electronjs.org/docs/latest/api/tray)
  を確認。Linux は StatusNotifierItem と GtkStatusIcon を使うが、トレイの
  作成成功だけでは画面上で操作できると判断できない。このため Linux は常に
  ウィンドウを閉じると終了する。Windows/macOS のトレイ常駐は変更しない。
- Linux でトレイ作成に失敗しても起動は続け、録音状態の取得と終了確認を維持する。
  録音を続けるときは最小化する。PC の再生音声の録音とログイン時の自動起動は表示しない。
- サンドボックスは有効のまま。root 起動や `--no-sandbox` を手順に含めない。

## modelshelf の同梱制限

[公式 v0.2.0 リリース](https://github.com/KOIYAL/modelshelf/releases/tag/v0.2.0) の
GitHub API と実ファイルを確認して、次の値を固定した。

| 項目 | 値 |
|---|---|
| Asset | `modelshelf-linux-x64` |
| サイズ | 3,945,592 bytes |
| SHA-256 | `5cc7d53f67efca282287ebb73ee46c21c5ce70a9febca8bdfa70a928d6237cfe` |
| URL | `https://github.com/KOIYAL/modelshelf/releases/download/v0.2.0/modelshelf-linux-x64` |

`objdump -T` で `GLIBC_2.39` への参照を確認した。Ubuntu 22.04 の glibc 2.35 では
起動できないため、ダウンロードとハッシュ確認後に `--version` を実行する。
失敗した場合は `LT_BUNDLE_MODELSHELF=0` を PyInstaller に渡し、同梱を省く。
通常は要約 UI が隠れ、文字起こし・録音・話者分離は使える。
利用者が別途動作する modelshelf を PATH や `MODELSHELF_BIN` で指定していれば、
従来どおりそのバイナリを利用できる。

新しい環境で `--version` が通る場合だけ同梱する。案内の末尾に glibc のバージョンと
同梱有無を書く。Ubuntu 22.04 対応の公式バイナリが提供されたら、URL・ハッシュ・
この制限をまとめて見直す。互換性を確かめず最新版へ追従しない。
CPU 用 llama-cpp-python のインデックスも実際に取得して確認した。
Electron Packager の引数はインストール済み 20.0.1 の型定義で確認した。

## 人が確認する項目

1. GitHub Actions を実行し、Ubuntu 22.04 でテストと tar.gz の作成が完了すること。
   artifact 名は `LocalTranscriber-linux-x64`。この作業では CI の起動・公開は行わない。
2. Ubuntu 22.04 と 24.04 の通常ユーザーでフォルダ全体を展開して起動する。
   GNOME/KDE、X11/Wayland で画面、ファイル選択、ダウンロードを確認する。
3. トレイあり・なしの両方で起動し、待機中のウィンドウを閉じるとバックエンドも終了すること。
   トレイがあるときは録音操作・書き出し先・保存先を開く操作も確認する。
4. マイク録音中と一時停止中に閉じる操作を行い、キャンセルで録音状態が保たれること。
   終了を選んだときはバックエンドが終了し、元の録音ファイルが残ること。
5. 実際の会議音声で文字起こしと任意の話者分離、TXT/SRT/VTT/JSON を確認する。
   モデル準備後はネットワークを切って同じ操作を試す。
6. CI ビルドでは要約 UI が隠れること。modelshelf 同梱のローカルビルドでは、
   初回準備とオフライン要約を確認する。音声・文字起こし・要約は外部送信しない。
7. `LT_UPDATE_CHECK=off` の起動、新版通知、再起動後の設定・モデル保存を確認する。

## この作業での確認結果

- pytest 129 件、偽 API による Node テスト 27 件が成功。変更 JS の `node --check`、
  `bash -n build-linux.sh`、workflow の YAML とトリガー・runner の確認も実施。
- Ubuntu 24.04 で `build-linux.sh` を最後まで実行し、
  `dist/LocalTranscriber-0.6.0-linux-x64.tar.gz`（285,303,324 bytes）を生成。
  アーカイブ内の案内・ライセンス・app.asar・実行ファイルと実行権限を確認。
- 同梱バックエンドの health/config API、要約と話者分離の依存読み込み、
  新版確認 OFF、SIGTERM 後の終了を確認。モデルの取得・推論は実行していない。
- `LT_BUNDLE_MODELSHELF=0` のバックエンドも別にビルド。起動と、要約が利用不可・
  話者分離が利用可能になることを確認した。

実機での音声処理、デスクトップごとの差、Ubuntu 22.04 の CI 実行は未確認。
配布前に上記の人による確認を行う。
