# 0.5.0 リリース手順（Windows ポータブル版）

0.5.0 の目玉は**ローカルLLM要約**。配布 zip に modelshelf.exe と
llama-cpp-python を同梱するため、ビルド手順が 0.4.0 から少し変わっている。
リポジトリ側の準備（バージョン更新・spec/ビルドスクリプト対応）は済み。

## Windows 側でやること

1. **リポジトリを最新化**

   ```bat
   git pull
   ```

2. **vendor\modelshelf.exe を配置**（gitignore 済みフォルダ）

   どちらか:

   ```bat
   :: A) GitHub Actions の成果物から（要 gh ログイン）
   gh run download --repo KOIYAL/modelshelf -n modelshelf-windows-x64 -D vendor

   :: B) WSL のチェックアウトからコピー（WSL 側に配置済み）
   mkdir vendor
   copy \\wsl.localhost\Ubuntu\home\zenkutsu\local-transcriber\vendor\modelshelf.exe vendor\
   ```

3. **ビルド**

   ```bat
   build-windows.cmd
   ```

   - vendor\modelshelf.exe が無いと最初に止まる（メッセージあり）
   - `[1/5]` で llama-cpp-python の CPU ホイールが入る。ホイールが見つからず
     ソースビルドが始まって失敗する場合は VS Build Tools + CMake が必要
     （通常はプリビルトが落ちてくるので不要のはず）
   - 完了すると `dist\LocalTranscriber-0.5.0-win-x64.zip` ができる

4. **動作確認**（配布前スモーク）

   `dist\electron\LocalTranscriber-win32-x64\LocalTranscriber.exe` を起動して:
   - [ ] 文字起こしが従来どおり動く
   - [ ] 完了画面に「要約する」ボタンが**表示される**（同梱が効いている証拠。
         出ない場合は modelshelf.exe / llama_cpp の同梱漏れ）
   - [ ] 要約を1回実行（初回はモデルDLが走る。~/.modelshelf に入る）
   - [ ] `SUMMARY.TXT` がダウンロードできる

5. **zip を website リポジトリに置いて連絡**

   ```bat
   copy dist\LocalTranscriber-0.5.0-win-x64.zip \\wsl.localhost\Ubuntu\home\zenkutsu\koiyal-website\downloads\
   ```

   ここまで来たら Claude に「zip できた」と伝える。以降（R2 アップロード →
   `src/content.ts` のバージョン/サイズ/URL 更新 → Pages デプロイ）はそちらで
   実施（アップロードとデプロイは実行前に確認を挟む）。

## メモ

- **サイズ**: llama-cpp-python(CPU) + modelshelf.exe で zip は 0.4.0 比 +50MB 前後の見込み
- **macOS 版**: `vendor/modelshelf`（macos-arm64 アーティファクト）を置けば
  同じ spec が同梱する。dmg ビルド時に同様の手順（未検証）
- **MS Store (MSIX) 版**: 同梱内容は同じなので `package-msix.cmd` は従来どおり。
  ストア審査観点で「追加の実行ファイル同梱」に言及が必要なら STORE_SUBMISSION.md 参照
- modelshelf.exe は静的 CRT でビルドしてあるので VC++ 再頒布は不要
