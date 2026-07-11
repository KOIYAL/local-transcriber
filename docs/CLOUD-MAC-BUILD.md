# クラウド Mac ビルド（GitHub Actions）

ローカル Mac なしで Mac アプリをビルド・署名・公証する仕組み
（EAS Build 相当）。Actions タブから **Build macOS app** を手動実行するか、
`v*` タグを push すると走る。

ランナーは `macos-26`（Apple Silicon / Xcode 26 = FoundationModels SDK 入り）
なので、Apple Intelligence ヘルパーのコンパイルまで含めて `build-macos.sh`
がそのまま動く。成果物は Actions の artifact
`LocalTranscriber-macOS-arm64`（DMG）。

## Secrets（リポジトリ Settings → Secrets and variables → Actions）

**未設定でも動く**: その場合は未署名のテストビルドになり、実行サマリーに
何が欠けていたか表示される。設定した瞬間から署名・公証が自動で有効になる。

| Secret | 内容 | 入手 |
| --- | --- | --- |
| `MAC_CERT_P12_BASE64` | Developer ID Application 証明書(.p12) を base64 化した文字列 | キーチェーンアクセスで書き出し → `base64 -i cert.p12 \| pbcopy` |
| `MAC_CERT_PASSWORD` | 上記 .p12 のパスワード | 書き出し時に設定したもの |
| `MAC_CODESIGN_IDENTITY` | 例: `Developer ID Application: 株式会社KOIYAL (TEAMID)` | `security find-identity -v -p codesigning` |
| `APPLE_API_KEY_P8_BASE64` | App Store Connect API キー(.p8) の base64 | App Store Connect → ユーザとアクセス → 統合 → App Store Connect API（ロール: Developer 以上） |
| `APPLE_API_KEY_ID` | 上記キーの Key ID | 同上の画面 |
| `APPLE_API_ISSUER_ID` | Issuer ID | 同上の画面 |
| `MODELSHELF_REPO_TOKEN` | KOIYAL/modelshelf を読める PAT（`repo` + Actions read） | modelshelf が private の間だけ必要。公開後はワークフローを無トークン化できる |

`MODELSHELF_REPO_TOKEN` が無い場合、ローカルLLMフォールバックは同梱されず
**Apple Intelligence 専用ビルド**になる（対応 Mac では要約が動く。非対応 Mac
では要約UIが出ないだけで文字起こしは通常どおり）。

## コストの目安

private リポジトリの macOS ランナーは消費分数が **10倍換算**
（無料枠 2000分/月 = mac 実質200分）。このビルドは 15〜25 分/回の想定なので、
リリース時の手動実行なら十分無料枠に収まる。push ごとの自動実行にはしない。

## クラウドで代替できないもの

- **Apple Intelligence の実機スモーク**: CI ランナーでは Apple Intelligence を
  有効化できない（Apple Account が必要）。ビルド・署名・公証は完結するが、
  要約機能の動作確認は配布前に実機 Mac で1回行うこと
  （`desktop/apple-intelligence-helper/README.md` の注意も参照 —
  Swift ヘルパーは初回コンパイル時に微修正が要る可能性がある。
  コンパイル自体はこのワークフローが検証してくれる）
- 証明書・API キーの**発行**（Apple Developer サイトでの一度きりの作業）
