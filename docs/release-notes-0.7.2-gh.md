## Local Transcriber 0.7.2

PCのメモリに合わせた文字起こしモデルの選び方を見直しました。

### 変わったこと

- **メモリ 8GB・16GB・32GB の Windows・Linux PC で、想定どおりのモデルを選ぶ**: Windows・Linux はシステムが確保する分だけ、アプリから見えるメモリが表示より少し少なくなります。判定に余裕を持たせ、8GB は Base、16GB は Small、32GB は Turbo を選ぶようにしました。Mac（ユニファイドメモリ）の選び方は変わりません（8GB は Base、16GB・24GB は Small、32GB 以上は Turbo）。
- 32GB の Windows PC で Small を使っている場合は、設定の「より良いモデルを確認」から Turbo へ切り替えられるようになります（確認つき。自動では切り替えません）。
- 設定・用語集・ダウンロード済みのモデルはそのまま使えます。

### 配布物

- Windows 10 / 11 (x64): `LocalTranscriber-0.7.2-win-x64.zip`
- macOS Apple Silicon: `LocalTranscriber-macOS-arm64.dmg`（未署名。初回は「システム設定」→「プライバシーとセキュリティ」→ 一番下の「セキュリティ」の「開く」→「このまま開く」で許可します）
- Linux x86_64（テストビルド）: `LocalTranscriber-0.7.2-linux-x64.tar.gz`

---

## Local Transcriber 0.7.2 (English)

- **The right model on 8, 16 and 32 GB Windows and Linux PCs**: these systems report slightly less memory than installed, so the automatic choice now leaves room for that. 8 GB PCs get Base, 16 GB get Small and 32 GB get Turbo. Mac (unified memory) choices are unchanged (8 GB Base, 16/24 GB Small, 32 GB or more Turbo).
- On a 32 GB Windows PC that uses Small, "Check for a better model" in Settings can now offer Turbo (with confirmation; never automatic).
- Settings, the glossary and downloaded models are kept.
