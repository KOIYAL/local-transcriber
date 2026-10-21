# 2026-10-21 コードレビューの反映（0.6.0 → 次版）

Codex（GPT）による全体レビューと Claude の確認を突き合わせ、本物と判断した指摘を直した。
番号は Codex の指摘順。P1 は実害のあるバグ、P2 は条件付きで起きる問題。

| # | 重要度 | 指摘 | 対応 | 変更箇所 |
|---|---|---|---|---|
| 1 | P1 | 127.0.0.1 バインドだけでは DNS rebinding と CSRF を防げない | Host ヘッダーがループバックでなければ 421、書き込み要求の Origin がページのホストと違えば 403 | `app/main.py` `local_only_guard` |
| 2 | P1 | チャンク送信に失敗すると録音セッションが残り、以後の録音が 409 になる。送信の reject が stop を素通りする | 送信は 3 回まで再試行し、失敗は chain 内で握って即時に警告。stop は必ず送り（失敗前までの録音を文字起こし）、stop が失敗したら DELETE で解放 | `app/static/recorder.js` |
| 3 | P1 | 文字起こし失敗時に元ファイルを削除する（アプリ内録音は唯一のコピー） | 削除は成功後だけ。失敗時は `data/uploads` に残す | `app/jobs.py` |
| 4 | P1 | Apple Intelligence の reduce ループが収束しないと要約ワーカーが永久に詰まる | 最大 4 周、縮まなければ切り詰めて最終要約へ | `app/apple_intelligence.py` |
| 5 | P2 | 録音の初期化失敗時にサーバー側セッションが残る | start の catch で DELETE | `app/static/recorder.js` |
| 6 | P2 | multipart を全部受けてから上限判定（一時ディスクを食う） | Content-Length が上限＋1MiB を超える `/api/jobs` POST は解析前に 413 | `app/main.py` |
| 7 | P2 | トレイが毎秒 `/api/jobs` で全文を取得 | 一覧は状態のみ（本文・要約文なし）。詳細は `/api/jobs/{id}` | `app/jobs.py` `as_dict(include_result=False)` |
| 8 | P2 | ジョブがメモリに無制限に溜まる | 直近 50 件を超えた分の完了・失敗ジョブを一覧から外す（ファイルは残す） | `app/jobs.py` `MAX_JOBS` |
| 9 | P2 | 「より良いモデルを確認」が常に false | 起動時はダウンロード済みモデルを優先して使い、推奨との差でアップグレード判定 | `app/model_manager.py` `_installed_or` |
| 10 | P2 | backend の spawn error を拾わず Electron ごと落ちる | `error` イベントを保持して起動ダイアログに出す | `desktop/main.js` |
| 11 | P2 | `will-navigate` が prefix 判定で別ポートや userinfo 付き URL を通す | backend の origin と厳密一致 | `desktop/main.js` |
| 12 | P2 | CUDA 検出時に float16 固定で、FP16 非対応 GPU はロード失敗し CPU 退避もしない | CUDA は `compute_type="auto"`、`ValueError` と "float16 / compute type" も CPU 退避の対象 | `app/transcriber.py` |

Codex の指摘以外で直したもの:

- 終了時に文字起こしスレッドが残ってプロセスが消えない（`os._exit` で確実に終了。元ファイルは残る）: `app/desktop.py`
- モデルを切り替えた後も前のモデルがメモリに残る（常駐は 1 つだけ）: `app/transcriber.py`
- ページの再読み込みなどで孤立した録音セッションは、起動時に stop して文字起こしに回す: `app/static/recorder.js` `recoverOrphanSession`
- backend の起動待ちを 30 秒から 90 秒に: `desktop/main.js`

提案のみ（挙動が変わるので本人判断）:

- `condition_on_previous_text=True`（faster-whisper デフォルト）は長い日本語音声で同じ文の繰り返しを起こしやすい。`scripts/transcribe_cli.py` 相当の個人用スクリプトでは False にしている。アプリ側も False にするか、繰り返し検出を入れるかは要検討。

実機での確認がまだのもの: 録音の失敗経路（recorder.js）はブラウザでの手動確認が必要。pytest は 68 件通過。
