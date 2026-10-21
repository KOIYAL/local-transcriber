# 0.7.0 リリース手順（社内向け）

対象は Windows x64 ポータブル ZIP、macOS Apple Silicon DMG、Linux x64 テスト用 tar.gz、
Microsoft Store 提出用の未署名 MSIX です。T6 はリポジトリのリリース準備までです。
0.7.0 の配布物は未生成・未確認で、タグ・push・公開・Store申請も実施していません。
Claude が差分と検証結果を確認し、オーナーの承認後にタグ・公開作業を行います。

## 変更点と原稿

日英の原稿は [GitHub Release 用リリースノート](release-notes-0.7.0-gh.md) にまとめています。
オンライン会議の音声、用語集、試験的な話者分離、Turbo の自動選択、新版通知、Linux ビルド、
MSIX CI に加え、[レビュー修正](review-fixes-2026-10-21.md) の12項目と追加修正も含めています。
同文書で提案扱いだった繰り返し抑制は T1 で実装済みです。後続レビューの設定保存、
各区間への用語集反映、話者分離の別プロセス化、PC音声のオリジン判定修正も含みます。

PC音声と話者分離はデフォルト OFF です。未対応環境では隠すか理由を表示します。
デスクトップの設定は `settings.json`、ブラウザは同じオリジンの localStorage を使います。
既存の文字起こしモデルと保存データを消さずに更新します。

## 1. バージョンと差分の確認

- [ ] `pyproject.toml`、`app/main.py`、`desktop/package.json`、`desktop/package-lock.json` の
  アプリバージョンが0.7.0であること。lockfile の依存パッケージの番号は変更しない。
- [ ] `build-windows.cmd` の ZIP 名が `LocalTranscriber-0.7.0-win-x64.zip` になること。
- [ ] macOS と Linux は Electron Packager が `desktop/package.json` の番号を使うこと。
  導入済み `@electron/packager/dist/infer.js` でこの動作を確認済み。
  Linux の tar.gz 名も同じ番号を読み、DMG 名は従来のままバージョンを含まない。
- [ ] Store の4桁の番号はアプリと別に管理する。ローカルのデフォルト `1.0.2.0` を
  申請番号として無条件に使わず、提出履歴より大きい番号を人が選ぶ。`0.7.0.0` にしない。
- [ ] `git diff` と計画書の進捗を確認。個人用 `scripts/transcribe_cli.py` は含めない。
  過去の0.6.0文書とテストの比較用バージョンは、そのまま残す。

## 2. ローカル検証

リリース対象のコミットで次を実行します。テストではネットワーク・実モデル・外部バイナリを使いません。

```bash
.venv/bin/python -m pytest -q
node --test tests/*.test.cjs
for file in desktop/*.js app/static/*.js; do node --check "$file"; done
bash -n build-macos.sh build-linux.sh
git diff --check
```

T6 の確認結果（2026-10-21）: pytest 150件、Node 33件、全JSの `node --check`、
bash構文確認、`git diff --check` が成功しました。導入済み Electron Packager でも
3 OS のアプリバージョンが0.7.0になることを確認しました。
これは GUI・権限・音声品質・配布物の動作確認の代わりにはなりません。
T4 で生成した0.6.0の Linux アーカイブは、今回の配布物として流用しません。

## 3. 配布物の作成

人が同じコミットを対象に3つの CI を手動実行し、先に動作確認します。
タグの push でも起動しますが、CI は artifact を作るだけで GitHub Release や Store へ公開しません。

| OS・用途 | CI 名 | artifact 名 | 中にあるファイル |
| --- | --- | --- | --- |
| Windows ポータブル | Build Windows app | `LocalTranscriber-win-x64` | `LocalTranscriber-0.7.0-win-x64.zip` |
| Windows Store | 同上 | `LocalTranscriber-msix` | `KOIYAL-Transcriber-Store.msix` |
| macOS Apple Silicon | Build macOS app | `LocalTranscriber-macOS-arm64` | `LocalTranscriber-macOS-arm64.dmg` |
| Linux x64 | Build Linux app | `LocalTranscriber-linux-x64` | `LocalTranscriber-0.7.0-linux-x64.tar.gz` |

- Windows: `build-windows.cmd`。`vendor/modelshelf.exe` が必要（CI は取得する）。
  MSIX は `package-msix.cmd`。CI の `STORE_IDENTITY_NAME`、`STORE_PUBLISHER`、
  `STORE_PACKAGE_VERSION` のいずれかが未設定なら、MSIX だけをスキップする。
  [Store申請メモ](../STORE_SUBMISSION.md) の本人確認・価格・提出番号の確認を先に行う。
- macOS: `./build-macos.sh`。[クラウドビルド](CLOUD-MAC-BUILD.md) と
  [Macリリース確認](../MAC_RELEASE.md) に沿って署名・公証を確認する。
  署名情報なしでは未署名テスト用になる。Intel は今回の配布対象に含めない。
- Linux: `./build-linux.sh`。Ubuntu 22.04 x86_64 を基準とする。
  modelshelf v0.2.0 は glibc 2.39 が必要なので、22.04 CI では同梱を省く。
  `START_HERE_LINUX.txt` のビルド環境と同梱有無を確認する。

最終ファイルのサイズと SHA-256、CI 実行・コミット・署名状況を記録します。過去のサイズを転記しません。
秘密情報の値を記録やリリースノートに書かないでください。

## 4. 実機確認（公開前に人が行う）

- [ ] Windows と macOS で初回起動・モデル準備・ファイル文字起こし・マイク録音・停止・
  一時停止・再開・破棄・無音警告・終了確認・トレイ再表示を確認する。
- [ ] TXT/SRT/VTT/JSON、全文コピー、要約と SUMMARY.TXT、指定した保存先、同名ファイルの
  連番保存を確認する。非対応環境では任意機能が隠れることも確認する。
- [ ] [PC音声の確認項目](system-audio-2026-10-21.md) に沿って、相手と自分の声、
  権限拒否、共有キャンセル・途中終了、Bluetooth、macOS の権限説明を確認する。
- [ ] [話者分離の確認項目](diarization-2026-10-21.md) に沿って、準備・再試行・話者ラベル・
  コピー・書き出し・要約を確認する。特に Windows/macOS の PyInstaller 配布物で子プロセスが
  起動し、処理中も API と録音チャンク保存が応答すること。長時間音声の時間・メモリ・精度も確認する。
- [ ] 用語集の名前が長い音声の後半でも参考にされること、同文の繰り返しが減ることを確認する。
  用語集・マイク・表示言語・PC音声の選択は、アプリ終了・再起動後も保持されること。
- [ ] 送信失敗・初期化失敗後に再録音できること、再読み込み後の録音回収、
  文字起こしや話者分離の失敗時に元音声・作成済みの出力が残ることを確認する。
- [ ] 0.6.0から更新し、既存モデル（Mediumを含む）を維持すること。32GB以上の環境では
  Turbo の手動更新候補、新規セットアップでは自動選択を確認する。
- [ ] モデル準備後、ネット接続なしで文字起こし・対応する任意機能を確認する。
  `LT_UPDATE_CHECK=off` で新版確認の通信が止まることを確認する。
  新版通知は偽応答を使うか将来のリリース時に確認し、無効時・失敗時は表示されないことも確認する。
- [ ] [Linux確認項目](linux-build-2026-10-21.md) に沿って Ubuntu 22.04、GNOME/KDE、
  X11/Wayland、トレイあり・なしで起動・マイク・終了確認・書き出しを確認する。
  ウィンドウを閉じると終了すること、要約の同梱有無が説明と合うことを確認する。
- [ ] MSIX の実生成・インストール・既存パッケージからの更新・認定キットを確認する。
  Store の画面に貼る画像は日英とも0.7.0で撮り直す。

Windows/macOS の話者分離同梱に問題があれば、配布前に同梱を外して UI を隠し、
ソース実行だけに限定します。その場合は README・リリースノート・Store掲載文も変更します。
未確認の機能を動作確認済みとして公開しないでください。

## 5. タグ・公開（承認後に Claude と人が行う）

1. 上記の結果を確認し、残る制約をリリースノートに反映する。0.7.0 の実ファイルを添付対象にする。
2. オーナーの承認後、確認済みコミットに `v0.7.0` タグを付けて push する。
   タグからの再ビルドを使う場合は、その成果物も確認する。
3. [日英原稿](release-notes-0.7.0-gh.md) の草稿用の段落を削除し、実際の添付ファイルと
   署名・公証状況に合わせて GitHub Release を作成する。未署名 MSIX は一般公開に含めない。
4. Store は [申請メモ](../STORE_SUBMISSION.md) に沿って別途申請する。GitHub の通知は
   Store 自動更新ではないことを掲載文・審査メモで確認する。
5. T7 の製品ページ更新には最終ファイル名と実サイズを渡す。別リポジトリの公開は T6 に含めない。
