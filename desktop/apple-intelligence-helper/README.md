# apple-intelligence-helper

Python バックエンドから Apple Intelligence のオンデバイスモデル
（FoundationModels framework、Swift 専用 API）を使うための極小ブリッジCLI。
`app/apple_intelligence.py` が subprocess + JSON で呼び出す。

## ビルド（macOS 26 以降の SDK が必要）

```bash
cd desktop/apple-intelligence-helper
swiftc -O -parse-as-library main.swift -o ../../vendor/apple-intelligence-helper
```

`vendor/` に置けば `desktop/backend.spec` が拾ってバックエンド実行ファイルの
隣に同梱し、`app/apple_intelligence.py` がそこから解決する
（`build-macos.sh` は SDK が対応していれば自動でこのビルドを行う）。
アプリ全体の deep codesign / 公証で一緒に署名される。

## 動作条件（実行時）

- Apple Silicon Mac + macOS 26 以降
- システム設定で Apple Intelligence が有効（地域・言語の条件あり）

満たさない場合は `check` が `{"available": false, "reason": ...}` を返し、
アプリは自動で modelshelf + llama.cpp 経路にフォールバックする。

## 注意

このコードは **macOS 実機での未検証スカフォールド**。API 名
（`SystemLanguageModel.availability` / `contextSize` /
`LanguageModelSession.GenerationError.exceededContextWindowSize`）は
macOS 26.4 時点のドキュメントに基づくが、初回ビルド時にコンパイラの指摘に
合わせて微修正が必要になる可能性がある。修正したら
`tests/test_apple_engine.py` が期待する JSON プロトコル
（`check` / `summarize` の入出力）だけ維持すること。
