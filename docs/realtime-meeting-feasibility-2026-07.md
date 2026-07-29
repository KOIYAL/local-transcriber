# 会議のリアルタイム文字起こしと即時要約: 実現性調査と設計

作成日: 2026-07-29 / 対象バージョン: Local Transcriber 0.5.0 / 本書はコード変更を伴わない調査・設計文書

表記ルール: 【確】は出典URLで確認した事実、【推】は本書の推測。数値は出典の記載をそのまま引用する。

---

## 1. 結論サマリー

### 1-1. オンライン会議対応: 可能。推奨は「システム音声キャプチャ方式（ボットなし）」

Zoom/Teams/Meet に録画ボットを参加させる方式はクラウド送信が前提になり、本製品の価値を壊す。
PC上で再生されている音声を直接取得する方式なら完全ローカルのまま実現でき、Notta も同じ方式に移行済み【確】。
Electron 42 を既に使っておりシステム音声取得は Electron 39 以降で標準サポートのため、追加ドライバは不要【確】。

### 1-2. オフラインMTG（対面）の録音ボタン: 可能。最小工数で、最初に出すべき機能

マイク録音だけなら OS 権限もマイク1本で済み、既存の「ファイル→JobManager→faster-whisper→要約」経路にそのまま合流できる。
新規追加は録音UI・PCM受け口・macOS のマイク権限まわりのみで、既存機能への影響はない。
Phase 1 として単体で出荷可能かつ、Phase 2 以降の土台がすべてここで揃う。

### 1-3. リアルタイム文字起こし: 可能。ただしOS別に分岐させるのが唯一の合理解

Whisper系はストリーミング設計ではなく、準リアルタイム運用では短い発話の精度が50〜60%まで落ちる【確】。
macOS 26 以降は Apple の SpeechTranscriber（完全オンデバイス・日本語対応・会議音声を設計目標に明記）が最良【確】。
Windows は faster-whisper のモデルを `kotoba-whisper-v2.0-faster` に差し替えたうえで LocalAgreement-2 方式を載せる。

**最重要の設計方針**: 会議中のリアルタイム表示は「暫定」、会議終了後の再処理を「確定」とする二段構え。
これによりリアルタイムASRの精度不足が最終成果物に伝播しない。

---

## 2. 競合比較

### 2-1. 主要製品

| 製品 | 音声取得方式 | ローカル完結 | 価格 | プラットフォーム | リアルタイム | 出典 |
|---|---|---|---|---|---|---|
| Notta デスクトップ | ①システム音声＋マイク（ボットなし）②Notta Bot（会議参加） | 標準はクラウド。プライバシーモードのみローカル（ベータ・**要約非対応**） | 年払 プレミアム ¥1,185/月、ビジネス ¥2,508/月 | Win 10(2004)+/11、macOS 12+（システム音声は13+） | あり | [notta.ai/desktop](https://www.notta.ai/desktop), [pricing](https://www.notta.ai/pricing) |
| Otter.ai (OtterPilot) | ボット参加 | クラウド | 無料300分/月、Pro $16.99/月 | Web/Mac/Win/iOS/Android | あり | [otter.ai/pricing](https://otter.ai/pricing) |
| tl;dv | ボット参加＋ボットなしデスクトップ | クラウド | Pro $18/user/月（年払）※三次情報 | デスクトップ＋モバイル | あり | [tldv.io/blog/bot-free-ai-note-takers](https://tldv.io/blog/bot-free-ai-note-takers/) |
| Fireflies.ai | ボット＋デスクトップのボットレス | クラウド | Pro $10/席/月（年払） | Win 10+/macOS 12+ | あり | [fireflies.ai/pricing](https://fireflies.ai/pricing) |
| Granola | システム音声のみ・ボットなし | **ハイブリッド**（後述） | Business $14/user/月 | macOS/Windows/iOS/Android | あり | [granola.ai/pricing](https://www.granola.ai/pricing) |
| superwhisper | ディクテーション主体＋会議録音 | オフラインモデル選択可（クラウドLLMも標準搭載） | Pro $8.49/月 | macOS/Windows/iOS | あり | [superwhisper.com](https://superwhisper.com/) |
| MacWhisper Pro | システム音声録音＋会議自動検出 | **完全ローカル** | €59 買い切り ※三次情報 | **Mac専用** | あり | [lumevoice.com/blog/macwhisper-pricing-2026](https://lumevoice.com/blog/macwhisper-pricing-2026/) |
| Meetily | ローカル録音 | **100%ローカル**（Parakeet/Whisper＋Ollama） | 無料・OSS | **macOS＋Windows** | あり | [github.com/Zackriya-Solutions/meetily](https://github.com/Zackriya-Solutions/meetily) |
| Vibe | ファイル＋システム音声＋マイク | **完全オフライン** | 無料・MIT | Mac/Win/Linux | あり | [github.com/thewh1teagle/vibe](https://github.com/thewh1teagle/vibe) |
| Anarlog（旧Hyprnote） | システム音声＋マイク・ボットなし | 既定ローカル（BYO APIキーでクラウド可） | Free / Pro $15/月 | Mac (Apple Silicon) 明示 | あり | [anarlog.so](https://anarlog.so/) |
| Recall.ai | ①Meeting Bot API ②Desktop Recording SDK | クラウド | $0.50/録画時間＋文字起こし$0.15/時 | Bot: 主要6サービス / SDK: Mac＋Win | あり | [recall.ai/pricing](https://www.recall.ai/pricing) |

### 2-2. 日本市場

| 製品 | 取得方式 | 処理 | 料金 | プラットフォーム | 出典 |
|---|---|---|---|---|---|
| Notta | ボット＋システム音声 | クラウド（プライバシーモードのみローカル・ベータ） | 上表 | Win/Mac/iOS/Android/Web | [notta.ai](https://www.notta.ai/) |
| Rimo Voice | ボット参加 | クラウド。国内保管・ISO27001・AI学習なし | Pro ¥4,950/月、Team ¥6,600/月 | Web＋iOS/Android | [rimo.app](https://rimo.app/) |
| toruno（リコー） | Web会議連携＋ファイル | クラウド。AmiVoice＋Azure＋Bedrock | ¥27,000/月（30時間）〜¥85,500/月（100時間） | **Windows のみ。Mac版は提供なし** | [toruno.biz](https://toruno.biz/) |
| Otolio（旧スマート書記） | 全参加者の音声を1台のPCで録音（連携不要） | クラウド。東京リージョン・ISO27001 | 非公開 | 記載なし | [smartshoki.com](https://www.smartshoki.com/) |
| AI GIJIROKU | 確認不能 | 確認不能 | 確認不能 | 確認不能 | 旧ドメインが無関係コンテンツを配信。alt.ai の製品ページは404。**サービス継続を一次情報で確認できず** |

### 2-3. この表から読み取るべきこと

**(a) 市場はすでに「ボット参加型」から「システム音声取得型」へ移行済み**【確】。
Notta 自身が「会議APIとの連携ではなく、端末上で再生されるシステム音声を取得する仕組みです」と明記している（[notta.ai/desktop](https://www.notta.ai/desktop)）。
背景として、Google Meet が 2026-03-25 にサードパーティ製ノートテイカーボットを既定DENYのキューに入れる変更を行ったとの報告があり（[tl;dv ブログ](https://tldv.io/blog/bot-free-ai-note-takers/)。ただし**競合ベンダーのブログが唯一の出典で Google 公式の裏取りができていない**）、
Microsoft は公式ドキュメントで「Real-time Media bots are not recommended for AI agent scenarios.」と明記している（[Microsoft Learn](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts)）【確】。

**(b) 「ボットレス」と「ローカル完結」はまったく別物**【確】。ここが最大の誤解ポイント。
Granola は自社ブログで local-first を名乗るが、その定義は「音声ファイルがサーバーに残らない」であり、
トランスクリプトは米国AWSに保存され要約はクラウドAIで行われる（[granola.ai/blog/local-first-ai-notetaker-vs-cloud](https://www.granola.ai/blog/local-first-ai-notetaker-vs-cloud)）。
Notta のプライバシーモードは**ベータかつAI要約に非対応**と公式が明記している【確】。

**(c) 「Windows対応 × 完全ローカル × 日本語 × 要約まで」を満たす商用製品は存在しない**【推】。
Meetily（OSS・英語圏製）が唯一近い。MacWhisper・Granola・Anarlog は Mac中心。
日本の主要3社（Rimo/toruno/Otolio）はすべてクラウド前提で、差別化軸は「国内データセンター」「AI学習なし」であり、
「そもそも外部に送信しない」という一段強い訴求は誰も取っていない。**ここが Local Transcriber の空白地帯**。

### 2-4. ボット参加API方式を採らない根拠（仮説の検証結果）

「ローカル完結を守るならキャプチャ方式一択」という仮説は**成立する**。各社APIの制約は以下【確】。

| API | 状態 | 決定的な制約 |
|---|---|---|
| Zoom RTMS | GA（一般提供） | ボット不要で参加者ごとの音声をWebSocket配信。ただし**Zoom Developer Pack クレジットによる従量課金**＝アカウント必須・外部送信前提 |
| Google Meet Media API | **Developer Preview** | 「the Google Cloud project, OAuth principal, **and all participants** must be enrolled in the Developer Preview Program」＝**全参加者の事前登録が必要で実質商用不可** |
| Microsoft Teams Real-time Media | 提供中 | Microsoft自身が「AIエージェント用途には非推奨」と明記。マネージドパートナー経由。**.NET/C#＋GPU付きWindows Server が必須**で「significant infrastructure investment」と記載 |
| Recall.ai | 商用 | $0.50/録画時間。クラウド経由 |

いずれもクラウドアカウント・従量課金・外部送信を伴い、「完全ローカル・アカウント不要・APIキー不要」と両立しない。

出典: [Zoom RTMS](https://www.zoom.com/en/realtime-media-streams/) / [Google Meet Media API](https://developers.google.com/workspace/meet/media-api/guides/overview) / [Teams Real-time Media](https://learn.microsoft.com/en-us/microsoftteams/platform/bots/calls-and-meetings/real-time-media-concepts) / [Recall.ai](https://www.recall.ai/pricing)

---

## 3. 技術方式の比較

### 3-1. 音声キャプチャ: OS別制約表

| 項目 | Windows | macOS |
|---|---|---|
| システム音声API | WASAPI loopback（`AUDCLNT_STREAMFLAGS_LOOPBACK`）【確】<br>プロセス単位loopback は Win10 build 20348+【確】 | Core Audio Process Taps（**14.2+**）【確】<br>ScreenCaptureKit（13+）【確】 |
| Electron の対応 | `audio: 'loopback'` / `'loopbackWithMute'` が**公式に Windows のみ**【確】 | Electron **39.0.0-beta.4+** で Chromium が CoreAudio Tap を既定化。旧方式へのフォールバックなし【確】 |
| 必要な権限 | ループバック単体には権限プロンプトなし【推・状況証拠は強い】<br>マイクは「デスクトップアプリのマイクアクセス」ON が必要【確】 | Taps: `NSAudioCaptureUsageDescription` ＋ TCC の `kTCCServiceAudioCapture`【確】<br>SCK: 画面収録権限【確】<br>マイクは `NSMicrophoneUsageDescription` が別途必要【確】 |
| 署名要件 | 通常の Authenticode | **Developer ID 署名＋公証が必須**。ad-hoc署名だと `'wat?'`(2003332927) で全滅【確】 |
| ストア配布 | MSIX で loopback を禁じる規定なし。専用capabilityも存在しない【確】。OBS等が Store 配布実績あり【確】 | 主要な会議アプリ（Granola / MacWhisper / superwhisper / Otter / Fathom / Audio Hijack）は**全社がMac App Store外の直販**【確】 |
| 落とし穴 | **音が鳴っていない間はデータが来ない**。自前で無音を挿入しないとマイクと時間軸がずれる【確】 | **権限がないと「無音の生きたストリーム」が返り、警告もエラーも出ない**【確】 |
| Python直叩き | PyAudioWPatch(Apache-2.0) / SoundCard(BSD-3) で可能【確】 | **不可**。sounddevice も SoundCard も macOS ループバック非対応【確】 |

出典: [WASAPI loopback](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording) / [Electron session.md](https://github.com/electron/electron/blob/main/docs/api/session.md) / [Electron desktopCapturer.md](https://github.com/electron/electron/blob/main/docs/api/desktop-capturer.md) / [Core Audio Taps](https://developer.apple.com/documentation/CoreAudio/capturing-system-audio-with-core-audio-taps) / [NSAudioCaptureUsageDescription](https://developer.apple.com/documentation/bundleresources/information-property-list/nsaudiocaptureusagedescription) / [NAudio WasapiLoopbackCapture](https://github.com/naudio/NAudio/blob/main/Docs/WasapiLoopbackCapture.md) / [sounddevice issue #553](https://github.com/spatialaudio/python-sounddevice/issues/553)

**重要な既存資産**: 本リポジトリは既に `electron ^42.4.0` を使っている（`desktop/package.json`）。
システム音声取得に必要な Electron 39 以降の条件を**すでに満たしている**。追加ライブラリも仮想オーディオドライバも不要。

**仮想オーディオデバイス（BlackHole等）は採用しない**【確】。
BlackHole は GPL-3.0 で、README に「A license is required for all non-GPLv3 projects」と明記されており、
プロプライエタリ配布には個別商用ライセンス契約が必要。加えてインストール時に再起動を促す。
（[github.com/ExistentialAudio/BlackHole](https://github.com/ExistentialAudio/BlackHole)）
なお Electron 公式も、BlackHole/Soundflower の言及を「macOS 12.7.6 以前の回避策」に限定している【確】。

**Granola が実際に要求している権限**【確】（[docs.granola.ai](https://docs.granola.ai/help-center/troubleshooting/transcription-issues)）:
macOS は「Microphone」と「Screen & System Audio recording」の両方、Windows は「Let desktop apps access your microphone」。
「requires macOS 13 or later, but works best on macOS 14.2 or above」という記述から、
13.x では ScreenCaptureKit、14.2+ では Core Audio Taps という二段構えを採っていると推測できる【推】。

### 3-2. マイクとシステム音声のミックス: 2ch分離（L=マイク / R=システム）を推奨

**単一ミックスではなく2chで保存する**。理由は以下【確】。

- AssemblyAI: 「Multichannel transcription is ideal when your recording setup allows for distinct audio channels」「Speaker Diarization and Multichannel transcription **cannot be used together**」（[出典](https://www.assemblyai.com/blog/multichannel-speaker-diarization)）
- OSS実装 meetvox（MIT）は「left channel is the mic, right channel is the system output」として分割投入し、**話者分離モデルなしで「You」/「Other」を確定**している（[github.com/alesloa/meetvox](https://github.com/alesloa/meetvox)）
- empy-recorder（MIT）も `getUserMedia`→L / loopback→R を `ChannelMergerNode` で合成する同じ構成（[github.com/madAsket/empy-recorder](https://github.com/madAsket/empy-recorder)）

**ffmpeg フィルタの選択**【確】（[ffmpeg-filters](https://ffmpeg.org/ffmpeg-filters.html)）:
`amix` は足し算して1本に潰すため L/R の話者帰属という最大の利点を失う。しかも `normalize` が既定ONで副作用がある。
`join` を使って出力レイアウトとマッピングを明示指定するのが最も事故が少ない。

サイズ目安: 16kHz/16bit/2ch で約230MB/時。長期保存するなら FLAC で約半分【推】。

### 3-3. クロックドリフト問題と、その回避

マイクデバイスとループバックデバイスは独立した水晶で動くため、民生グレードで最悪100ppm差、
**1時間で180〜360msの累積ずれ**が生じる【推・計算値】。Recall.ai は実際にサンプルレートすら一致しない事例を報告している
（システム48kHz stereo float / マイク44.1kHz mono float。[出典](https://www.recall.ai/blog/how-i-built-a-botless-meeting-recorder-from-scratch)）。

Speex のマニュアルはこの問題を直截に述べている【確】:
「Using a different soundcard to do the capture and playback will *not* work, regardless of what you may think」
（[speex.org/docs/manual](https://www.speex.org/docs/manual/speex-manual/node7.html)）

**回避策の優先順位**【推】:
1. **Electron の単一 AudioContext 内で合成する**。クロックが1本化されるので**問題自体が消える**。本件はこれで足りる。
2. macOS でネイティブ実装が必要になった場合は private aggregate device ＋ drift correction（`kAudioSubDeviceDriftCompensationKey`）
3. ホストタイムスタンプ基準の書き込み＋ soxr による適応リサンプリング

### 3-4. エコー（自分の声が二重に入る）問題

スピーカー使用時、自分の声がマイクとシステム音声の両方に乗る。

**会議アプリ側のAECは助けにならない**【推・根拠は確】。Zoom/Meet がエコー除去するのは
「アプリ自身が `getUserMedia` したトラック」であり、`echoCancellation` は MediaStreamTrack 単位の制約。
こちらが独立に開いた生マイクキャプチャには一切適用されない。

**最も低リスクな設計は Chromium に任せること**【推】:
マイクを `getUserMedia({audio:{echoCancellation:true}})` で取得すれば、Chrome のソフトウェアAECが
「an internal loopback to get the playout audio to cancel」を参照信号として使う（[Chrome Developers](https://developer.chrome.com/blog/more-native-echo-cancellation/)）【確】。
Microsoft 自身も「WASAPI provides loopback mode **primarily to support acoustic echo cancellation**」と明記しており、
この設計は想定内の使い方【確】。

**フォールバック階層**【推】:
① ヘッドホン推奨UI（コストゼロで最も確実）→ ② Chromium側AEC → ③ Python側で `pywebrtc-audio`（Apache-2.0、WebRTC AEC3）による後処理

なお Recall.ai は AEC を使わず、オフラインで位置合わせして「slightly lower gain on the microphone path」で混ぜるだけ、と述べている【確】。

**実務Tips**【確】: Bluetoothヘッドセットは高品質出力とマイク入力を同時にできない。Granola は公式ヘルプで内蔵マイクの使用を案内している。検出してバナーを出すべき。

### 3-5. ASR: 日本語という制約が設計を決める

日本語CER比較（低いほど良い。出典 [kotoba-whisper-bilingual-v1.0](https://huggingface.co/kotoba-tech/kotoba-whisper-bilingual-v1.0)）【確】

| モデル | CommonVoice8 | JSUT | ReazonSpeech held-out（実会話に近い） |
|---|---|---|---|
| whisper-small | 15.1 | 14.2 | **41.5** |
| whisper-medium | 11.5 | 10.0 | **33.2** |
| whisper-large-v3 | 8.5 | 7.1 | 14.9 |
| **kotoba-whisper-v2.0 (756M)** | 9.2 | 8.4 | **11.6** |
| reazonspeech-nemo-v2 (619M) | 9.1 | 7.4 | **11.2** |

**この表が意味すること**: 英語なら「small に落として低遅延化」が成立するが、
**日本語では small/medium は実用外**（実会話でCER 33〜41%）。
現行の `app/system_info.py` は RAM 16GB未満で base/tiny を選ぶが、日本語会議では使い物にならない。
一方 kotoba-whisper-v2.0 は large-v3 の約半分のサイズで large-v3 を上回る日本語精度を出す。

**kotoba-whisper-v2.0 は faster-whisper 形式（CTranslate2）で公式配布されている**【確】。
つまり `kotoba-tech/kotoba-whisper-v2.0-faster` を `app/model_manager.py` のモデル候補に足すだけで、
**推論コードを一行も変えずに日本語精度を跳ね上げられる**。Apache-2.0。large-v3比6.3倍高速。
**本調査で判明した中で最も費用対効果が高い一手**。

### 3-6. ストリーミング方式の比較

**faster-whisper 自体にストリーミングAPIは無い**【確】。v1.2.1（2025-10-31）が最新で、
あるのは BatchedInferencePipeline（スループット向上であって低遅延化ではない）と Silero VAD フィルタのみ。
README は whisper_streaming / WhisperLive を「Community integrations」として外部紹介する立場（[releases](https://github.com/SYSTRAN/faster-whisper/releases)）。

| 方式 | ポリシー | 遅延 | CPU可否 | ライセンス |
|---|---|---|---|---|
| whisper_streaming (ufal) | LocalAgreement-2 | **3.3秒**（論文値） | 可 | MIT |
| SimulStreaming (ufal) | AlignAtt | WhisperStreaming比 約5倍高速 | **不可**（README が「10GB VRAM以上のGPU推奨。CPUではリアルタイムに遅すぎる」と明記） | MIT |
| WhisperLiveKit | 両対応 | 数値公開なし | 可 | Apache-2.0 |
| whisper.cpp stream | スライディング窓 | `--step` 既定500ms | 可 | MIT |

出典: [whisper_streaming](https://github.com/ufal/whisper_streaming) / [SimulStreaming](https://github.com/ufal/SimulStreaming) / [LocalAgreement-2 論文](https://arxiv.org/abs/2307.14743) / [WhisperLiveKit](https://github.com/QuentinFuxa/WhisperLiveKit)

**whisper.cpp stream の品質問題は未解決**【確】。README 自ら「a very basic VAD detector is used」と認め、
issue #426「Improvements to chunking for the stream example」は**2023-01起票で今も open**（[issue #426](https://github.com/ggml-org/whisper.cpp/issues/426)）。

**日本語固有の注意**【確】: whisper_streaming の文分割器は日本語を mosestokenizer でカバーせず、
wtpsplit（torch＋ニューラルモデルが必要）にフォールバックする。追加依存と追加レイテンシの要因になる。

### 3-7. 真のストリーミング対応ローカルASR（2026年7月時点）

| モデル | ストリーミング | 日本語 | ライセンス | CPU | レイテンシ | 出典 |
|---|---|---|---|---|---|---|
| **Apple SpeechTranscriber** (macOS 26+) | あり（volatile→finalized） | あり | OS標準 | ANEで実行 | 即時 | [developer.apple.com](https://developer.apple.com/documentation/speech/speechanalyzer) |
| Vosk ja (small 48MB / big 1GB) | あり | あり | Apache-2.0 | 可（RPi級） | 低（実測未確認） | [alphacephei.com/vosk/models](https://alphacephei.com/vosk/models) |
| Nemotron 3.5 ASR Streaming 0.6B | あり（cache-aware） | あり（ja-JP明記） | OpenMDW-1.1（商用可） | **記載なし・NVIDIA GPU前提** | 80/160/320/560/1120ms 可変 | [HuggingFace](https://huggingface.co/nvidia/nemotron-3.5-asr-streaming-0.6b) |
| Moonshine Streaming | あり | **英語のみ** | MIT | CPU専用設計 | 34–107ms (Mac) | [github.com/usefulsensors/moonshine](https://github.com/usefulsensors/moonshine) |
| Moonshine base-ja (58M) | なし | あり | **Moonshine Community License**（年商100万USD超は別途契約＋表示義務） | 可 | 未計測 | 同上 |
| sherpa-onnx ja ReazonSpeech (159M) | **なし**（オフライン専用） | あり | Apache-2.0 | 可・**RTF 0.054 (int8)** | VAD区切り依存 | [k2-fsa.github.io/sherpa/onnx](https://k2-fsa.github.io/sherpa/onnx/) |
| kotoba-whisper v2.0 (756M) | なし（チャンク） | あり | Apache-2.0 | 可 | 未計測 | 上記 |
| **Parakeet tdt-0.6b-v2/v3, Canary** | 一部あり | **日本語なし** | CC-BY-4.0 | 一部 | 未計測 | [HuggingFace](https://huggingface.co/nvidia/parakeet-tdt-0.6b-v3) |
| Kyutai STT | あり | **なし**（en/fr） | CC-BY-4.0 | 不可（MLXでMac可） | 0.5s / 2.5s | [github.com/kyutai-labs](https://github.com/kyutai-labs/delayed-streams-modeling) |

**要点**【確】:
- **Parakeet / Canary には日本語が一切ない**。v3の25言語はすべて欧州言語。当初仮説どおり日本語では使えない。
- **sherpa-onnx に日本語のストリーミングモデルは存在しない**（ストリーミングZipformerは中・英・韓・仏・ベンガルのみ）。
  ただし日本語 ReazonSpeech のオフラインモデルは int8 で CPU RTF 0.054（18倍速）と非常に速く、
  VAD区切りの擬似ストリーミングで体感遅延を十分小さくできる【推】。
- **ReazonSpeech にストリーミング版は無い**。
- **Nemotron 3.5 ASR Streaming が唯一の「日本語×真ストリーミング×商用可」**。ただし
  ベンチはすべてH100、Runtime Engine は NeMo 26.06、対応HW記載はNVIDIA GPUのみ。**CPU動作は未確認で最大の空白**。

### 3-8. Apple SpeechAnalyzer / SpeechTranscriber（macOS 26）は全項目クリア

| 項目 | 結果 | 出典 |
|---|---|---|
| サードパーティ利用 | 可（Speech framework の公開API） | [SpeechAnalyzer](https://developer.apple.com/documentation/speech/speechanalyzer) |
| 最低OS | macOS 26.0 / iOS 26.0 | Apple公式docs |
| 完全オンデバイス | 「Our new, on-device model」 | [WWDC25 session 277](https://developer.apple.com/videos/play/wwdc2025/277/) |
| 日本語 | あり（後述） | |
| ストリーミング | AsyncSequence入出力。**volatile results（即時の粗い結果）→ finalized results** | 同上 |
| 長尺・遠距離 | 「long-form and distant audio, such as **lectures, meetings, and conversations**」と明示 | 同上 |
| モデル配布 | `AssetInventory` でOSがDL。**アプリの配布サイズもランタイムメモリも消費しない**。OSが自動更新 | 同上 |

日本語対応の根拠【確】: 開発者API上の対応ロケールは `SpeechTranscriber.supportedLocales` の実行時クエリのため
Apple の静的リストは存在しないが、同一エンジンを使う機能で日本語が公式に明記されている
（[apple.com/macos/feature-availability](https://www.apple.com/macos/feature-availability/) の Call Transcription / Audio Message Transcription に Japanese (Japan)）。
第三者実装の補強として [swift-speech-analyzer](https://github.com/DravenYe/swift-speech-analyzer) が `--lang ja-JP` を対応言語表に明記。

**本リポジトリとの適合性が極めて高い**: 既に `desktop/apple-intelligence-helper/main.swift` という
「Swiftヘルパーを subprocess で呼び、JSON を stdin/stdout でやり取りする」パターンが実装済みで、
`docs/CLOUD-MAC-BUILD.md` によりCIランナーは `macos-26`（Xcode 26）。
**同じ設計をそのまま流用でき、ビルド基盤も既に揃っている**。

【推・未確認】Apple Intelligence の有効化が必要かは公式に明記がない。
SpeechTranscriber は Speech framework 側で Apple Intelligence 機能群とは別枠のため不要と推測するが、実機確認が必要。
`supportedLocales` / `isAvailable` で実行時判定する設計にすべき。

### 3-9. Windows のオンデバイス音声API は現時点では使えない

新API `Microsoft.Windows.AI.Speech` は存在する（バッチ＋ストリーミング両対応・完全オンデバイス）
（[Microsoft Learn](https://learn.microsoft.com/en-us/windows/ai/apis/speech-recognition)）が、採用不可の理由が3つ【確】。

1. **Experimental チャネル止まり**。WinAppSDK 2.2.2-experimental9（2026-06-09）が初出で Stable 2.3.1 には含まれず、
   Microsoft自身が「APIs may change, be removed, or never ship」と明記。
2. **言語指定APIが1つも無く、日本語音声が英訳されて返る**。
   未解決の公式issue [WindowsAppSDK #6640](https://github.com/microsoft/WindowsAppSDK/issues/6640)（2026-07-20起票・open・**Microsoftからの返信0件**）。
3. **MSIXパッケージ必須＋`systemAIModels` capability 必須**。CPU推奨要件も「4物理コア・3GHz・L3キャッシュ32MB以上」で一般的なノートPCの多くが未達。

参考として、レガシーの `Windows.Media.SpeechRecognition` は自由発話ディクテーションが**クラウド実行**（10秒上限）のため議事録用途に使えない【確】。

**結論**: Windows は当面 faster-whisper（＋kotoba-whisper）を継続する。Windows AI Speech は issue #6640 の解決と Stable 昇格を待ってウォッチ対象とする。

### 3-10. 端末負荷: これが「会議中に使えるか」を決める

whisper.cpp discussion #89 の実測（30秒窓のエンコード時間）【確】（[出典](https://github.com/ggml-org/whisper.cpp/discussions/89)）

| CPU | small | medium | large |
|---|---|---|---|
| MacBook M1 Pro (8スレッド) | 685ms | 1,928ms (RTF 0.064) | 3,350ms |
| i7-11800H ノート (8スレッド) | 4,829ms (RTF 0.161) | 未計測 | 27,740ms (RTF 0.925) |
| i5-8250U 薄型ノート | 未計測 | 未計測 | 61,548ms (**RTF 2.05 = 破綻**) |

**メンテナ ggerganov のコメント**【確】:
「going beyond 8 threads does not help regardless of how many cores you have. My guess is that the computation is **memory-bound**」
つまり**8スレッドで頭打ちかつメモリ帯域律速**。コア数を増やしても効かない。

**ストリーミングのオーバーヘッドは実在する**【確】。Android実測で「ライブ文字起こしは実時間の約5倍遅いのにバッチは速い」
（[discussion #3567](https://github.com/ggml-org/whisper.cpp/discussions/3567)）。

**リアルタイム精度の壁**【確】: large-v3 の準リアルタイム運用で短いセグメントは**50〜60%の精度**、
会議など長いセグメントでも80%台止まり（[discussion #3890](https://github.com/ggml-org/whisper.cpp/discussions/3890)）。
**これが「ライブは暫定・終了後に確定」の二段構えが必須である決定的根拠**。

**Apple Silicon の電力優位**【確】: whisper.cpp の ANE直接バックエンドは CoreML比 1.9〜2.0倍速かつ
**消費電力が約1/5**、品質劣化なし（cosine 0.999）（[discussion #3903](https://github.com/ggml-org/whisper.cpp/discussions/3903)）。
Apple 純正モデルは OS 側が ANE で回すため、この最適化を自前でやる必要すらない。
「会議中にファンが回らない・バッテリーが減らない」は商品価値そのもの【推】。

**実装上の罠**【確】:
- `GGML_BLAS=1` でビルドすると `-t` も `OMP_NUM_THREADS` も無視され1コアしか使わない（2026-03起票・未解決。[issue #3724](https://github.com/ggml-org/whisper.cpp/issues/3724)）
- 量子化は q8_0 / q4_0 を使う。**q5_0/q5_1 は旧CPUで3〜5.5倍遅く、q2_k は「hallucination and gibberish」**
- バッチ推論は使わない（RAM 1,477MB→3,608MB）

### 3-11. 話者分離（diarization）のローカル実装

| 手段 | ライセンス | オンライン対応 | 判断 |
|---|---|---|---|
| **2ch分離（L=自分 / R=相手）** | なし | 該当せず | **まずこれ。モデル不要で「自分」と「相手」は確定できる** |
| pyannote.audio 4.0.7 | MIT / community-1 は CC-BY-4.0 | オフライン | 商用利用は可。**問題は配布UX**（後述） |
| diart | MIT | **あり**（CPUで segmentation 11-12ms / embedding 26ms、遅延500ms〜5s可変） | 実用圏。ただし README が `pyannote.audio<3.1` を推奨＝4.x系と整合していない |
| sherpa-onnx | Apache-2.0 | **なし**（APIクラス名が `OfflineSpeakerDiarization`） | オフライン後処理用 |
| streaming Sortformer v2 | CC-BY-4.0 | あり（0.32/1.04/10.0/30.4s、最大4話者） | CPU実測未確認 |
| `diar_sortformer_4spk-v1` | **CC-BY-NC-4.0（非商用）** | 対象外 | **採用不可** |
| Revai reverb-diarization-* | **Rev Model Non-Production License（商用全面禁止）** | 対象外 | **採用不可。GitHub側LICENSEはApache-2.0だがREADMEが「applies only to the code not the models」と明言しており、バッジだけ見ると事故る** |

**pyannote の実際の問題はライセンスではなく配布UX**【確】。
ゲート文に商用禁止の文言はなく MIT / CC-BY-4.0 でいずれも商用可。
しかし**エンドユーザーにHuggingFaceトークン取得と条件同意を求める設計は成立しない**ため、重みを自社インストーラに同梱する必要がある。
**gatedリポジトリの重み再ホストが HuggingFace 利用規約に抵触するかは未確認**で、法務確認ポイント。

また WhisperX は 3.1（MIT）ではなく **community-1（CC-BY-4.0）** に依存しており、**帰属表示義務が製品に降ってくる**【確】。

---

## 4. 推奨アーキテクチャ

### 4-1. 設計原則

1. 既存の「ファイル → JobManager → TranscriptionEngine → exporters」経路は一切壊さない。会議機能は**別の入口**として足し、合流点を `JobRecord` に置く。
2. 音声キャプチャは **renderer（Electron/Chromium）側**で行う。理由は3つ。
   - `http://127.0.0.1` は potentially trustworthy origin なので `navigator.mediaDevices` がそのまま使える（[MDN Secure Contexts](https://developer.mozilla.org/en-US/docs/Web/Security/Secure_Contexts)）【確】。現行 `desktop/main.js` は `mainWindow.loadURL(backendUrl)` でUIを配信しており、この前提を満たす。
   - 単一 AudioContext 内で合成すればクロックドリフトが消える（3-3）
   - Python側にOS別オーディオライブラリを追加すると PyInstaller 同梱物とOS別分岐が増え、macOS署名も複雑になる
3. リアルタイム経路はバックエンドが「確定テキストの追記」だけを持ち、UIは既存の1秒ポーリング（もしくはSSE）で読む。

### 4-2. 追加する backend モジュール

| ファイル | 役割 |
|---|---|
| `app/capture.py`（新規） | 録音セッションの状態機械。`RecordingSession`: id / started_at / sources / wav_writer / リングバッファ / status。受け取ったPCMを16kHz float32へ正規化し、(a) セッションWAVへ追記 (b) ストリーミングASRのキューへpush |
| `app/streaming.py`（新規） | 逐次ASR。**エンジンを差し替え可能なインターフェース**にする（`faster_whisper` / `apple_speech` / 将来の別ASR）。VADで発話区間を切り、LocalAgreement-2で「確定」「暫定」を分離 |
| `app/meeting_summary.py`（新規） | 会議用の構造化要約。**既存の `SummaryEngine` / `AppleIntelligenceEngine` をエンジンとしてそのまま再利用**し、プロンプト（instructions）だけを差し替える |
| `app/exporters.py`（変更） | `to_minutes_md()` を追加（議事録Markdown） |
| `app/model_manager.py`（変更） | 日本語環境では `kotoba-whisper-v2.0-faster` を選ぶ分岐を追加 |
| `app/system_info.py`（変更） | 現行の RAM 16GB未満で base/tiny という選択は日本語会議では実用外（3-5）。会議用途のモデル下限を引き上げる |

### 4-3. 既存資産で「足さなくてよい」もの

- **VAD**: `faster_whisper/assets/silero_vad_v6.onnx` が既に同梱されており、`faster_whisper.vad.get_speech_timestamps` がそのまま使える。**追加依存ゼロ**【確・実機確認済】
- **音声デコード/リサンプル**: `desktop/backend.spec` が PyAV(`av`) を同梱済み。ffmpeg 相当の処理が既にある
- **numpy入力**: faster-whisper 1.2.1 の `WhisperModel.transcribe()` は `str | BinaryIO | np.ndarray` を受け付ける。**中間ファイルを書かずにチャンクを直接渡せる**【確・実機確認済】
- **Swiftヘルパーの呼び出しパターン**: `app/apple_intelligence.py` の subprocess＋JSON方式をそのまま SpeechTranscriber に流用できる
- **Electron のバージョン**: 42.4.0 で loopback 要件（39+）を満たす

### 4-4. 追加する API（`app/main.py`）

```
POST /api/recordings              セッション開始（sources: mic | system | both）→ recording_id
POST /api/recordings/{id}/chunk   PCMチャンク投入
GET  /api/recordings/{id}         状態＋確定セグメント＋暫定テキスト
POST /api/recordings/{id}/stop    停止。内部で JobManager.submit() を呼び、
                                  録音WAVを通常ジョブとして高精度に再文字起こし → 既存フローへ合流
GET  /api/recordings/{id}/events  （任意）SSE。ポーリングより滑らかだが必須ではない
```

### 4-5. 追加する frontend

| ファイル | 内容 |
|---|---|
| `app/static/recorder.js`（新規） | **MediaRecorder ではなく AudioWorklet を使う**（MediaRecorderはコンテナ単位で遅延が出て逐次処理に不向き）。mic と system を `ChannelMergerNode` で L/R に合成し、250ms間隔で backend へ送出 |
| `app/static/index.html`（変更） | 「録音」セクションを追加 |
| `app/static/app.js`（変更） | `translations` に録音系キーを EN/JA 両方追加（既存の i18n 規約に従う） |
| `app/static/styles.css`（変更） | 録音UI・ライブ字幕表示 |

### 4-6. `desktop/main.js` と配布まわりの変更

- `session.setDisplayMediaRequestHandler()` を設定し、Windows は `audio: 'loopback'` を指定
- **録音中はウィンドウを閉じてもプロセスを維持**（トレイ常駐）。会議中の実用上ほぼ必須
- **macOS: `entitlements.mac.plist` に `com.apple.security.device.audio-input` を追加**。現行ファイルには存在しない
- **macOS: Info.plist に `NSMicrophoneUsageDescription` と `NSAudioCaptureUsageDescription` を追加**。`build-macos.sh` は現在これらを設定していない
- **macOS: ヘルパーバイナリは必ず .app 内に置く**。macOS 26.1 で「.appバンドルでない素の実行ファイルが Screen & System Audio Recording リストに表示されない」バグがある（[Apple Developer Forums](https://developer.apple.com/forums/thread/807898)）【確】
- **ヘルスチェックを必ず実装する**。macOSは権限なしで無音の生きたストリームが返り警告も出ず、Windowsは音が鳴っていないとデータが来ない。**「録れているつもりで無音」が両OSで起きる**

### 4-7. 合流点（この設計の要）

録音停止 → 保存済みWAVを `JobManager.submit()` に渡すだけで、**既存の exports / summary / ダウンロードUIがそのまま使える**。

- リアルタイム表示 = 「速いが粗い暫定」
- 停止後の再文字起こし = 「遅いが正確な確定」

この二段構えなら、リアルタイムASRの精度が50〜60%であっても最終成果物の品質は落ちない。
**Phase 3 の技術リスクを Phase 1/2 の資産で吸収できる**構造になっている。

### 4-8. 即時要約の設計

既存の要約エンジン層（Apple Intelligence 優先 → ローカルLLM フォールバック）を**そのまま流用できる**。
変えるのはプロンプトと後処理だけ。

会議特有の構造化出力:
```
## 概要（3行）
## 決定事項
## 宿題 / ToDo（担当・期限）
## 次回日程
## 未決・持ち帰り
```

**注意点**【推】: `app/apple_intelligence.py` のコンテキストは約4096トークン共有で、
既に map-reduce 方式（チャンク要約 → 最終パス）が実装済み。1時間の会議は確実に複数チャンクになる。
決定事項や日程は「どのチャンクに出たか」に依存するため、
チャンク要約側の instructions に「決定事項・日付・担当者名・数値は必ず原文のまま残す」を明示する必要がある。
現行の `INSTRUCTIONS_CHUNK` は「essential facts and decisions」までしか指定していない。

**「即時」の実現**: 会議終了ボタンを押した時点で、リアルタイム経路が既に暫定トランスクリプトを持っている。
これを即座に要約エンジンへ流せば**待ち時間ゼロで暫定要約**が出せる。
その裏で高精度な再文字起こしを走らせ、完了後に要約を差し替える。この体験は Notta に対する明確な優位点になる【推】。

---

## 5. 段階的な実装計画

### Phase 1: オフライン録音ボタン ＋ 録音後文字起こし（最小）

| 項目 | 内容 |
|---|---|
| スコープ | マイク録音のみ。録音 → 停止 → 既存ジョブへ合流 → 文字起こし → 要約 |
| 追加 | `app/capture.py`、`app/static/recorder.js`、録音API 3本、録音UI、i18n、macOS権限（entitlements＋Info.plist） |
| **工数目安** | **3〜5人日**（実装2〜3日、Windows/macOS実機スモークとストア文言更新1〜2日） |
| 技術リスク | **低**。既存経路にほぼ乗るだけ。最大の不確定要素は macOS のマイク権限が署名・公証フローと噛み合うかの実機確認 |
| 出荷可能性 | **単体で出荷可能**。「対面の打合せを録音してそのまま議事録」だけでも訴求は立つ |

### Phase 2: システム音声キャプチャでオンライン会議対応

| 項目 | 内容 |
|---|---|
| スコープ | `getDisplayMedia` ＋ loopback でシステム音声取得、L/R 2ch合成、ヘッドホン推奨UI、トレイ常駐 |
| **工数目安** | **5〜8人日**（Windows 2日、macOS 3〜4日、権限UX・エラー処理・実機検証 2日） |
| 技術リスク | **中**。macOS の権限まわりが最大の変数。①権限がないと無音ストリームが黙って返る ②Developer ID署名＋公証が必須 ③macOS 13 と 14.2+ で API が異なる（ScreenCaptureKit / Core Audio Taps） |
| 事前に潰すべきこと | Windows: 無音時にデータが来ない問題への無音挿入。macOS: `audio:'loopbackWithoutChrome'` が Electron で通るかの実機検証（**未文書だがコードパス上は通る**【推】） |
| フォールバック | Chromium 経由で不足なら AudioTee（MIT、Swift CLI）を .app 内に同梱して subprocess 起動する経路がある |

### Phase 3: リアルタイム逐次表示

| 項目 | 内容 |
|---|---|
| スコープ | `app/streaming.py`、OS別ASR分岐、暫定/確定の2段表示UI |
| 内訳 | Windows: kotoba-whisper-v2.0-faster ＋ LocalAgreement-2（3〜4人日）<br>macOS: Apple SpeechTranscriber の Swift ヘルパー実装（4〜6人日。ただし `apple-intelligence-helper` のパターン流用で短縮可） |
| **工数目安** | **8〜13人日** |
| 技術リスク | **高**。①リアルタイム精度が50〜60%まで落ちる（二段構えで吸収）②端末負荷（i5-8250U級では large が RTF 2.05 で破綻）③Apple SpeechTranscriber の日本語ロケール・Apple Intelligence 依存が実機未確認 |
| 先に単独で出せる改善 | **モデルを kotoba-whisper-v2.0-faster に差し替えるだけなら 1〜2人日**でリアルタイム化を待たずに日本語精度が跳ね上がる。**Phase 1 と並行して最初にやるべき** |

### Phase 4: 話者分離・会議要約テンプレ

| 項目 | 内容 |
|---|---|
| スコープ | 2ch分離による「自分/相手」ラベル（**モデル不要**）、`meeting_summary.py`、議事録Markdown出力 |
| **工数目安** | **4〜7人日**（2ch話者ラベル1日、会議要約テンプレ＋map-reduce調整2〜3日、議事録エクスポート1日、評価1〜2日） |
| 技術リスク | **中**。真の多人数話者分離（pyannote / diart）はライセンスではなく**配布UX**（HFトークン・重み同梱・再ホストの規約適合）が壁。**Phase 4 では 2ch ラベルまでに留め、多人数分離は Phase 5 以降に切り離すことを推奨**【推】 |

### 累計と順序の推奨

合計 20〜33人日。ただし**この順序で出す必要はない**【推】。推奨順は以下。

1. **kotoba-whisper 差し替え（1〜2人日）**: 単独で価値があり、以降すべての精度前提になる
2. **Phase 1（3〜5人日）**: 単体出荷可能
3. **Phase 4 の会議要約テンプレ部分（2〜3人日）**: Phase 1 の録音と組み合わせるだけで「議事録アプリ」を名乗れる
4. **Phase 2（5〜8人日）**: ここで初めてオンライン会議に対応
5. **Phase 3（8〜13人日）**: 最後。リスクが最も高く、かつ前段の資産があれば失敗しても損失が限定される

---

## 6. Local Transcriber の立ち位置への影響

### 6-1. 「完全ローカル」は競合に対してどう効くか

**効く。しかも今が空白地帯**【推・根拠は2-3】。

- Notta のプライバシーモードは**ベータかつ要約非対応**。「ローカルで文字起こしできるが要約はクラウド」という中途半端な状態
- Granola の local-first は「音声ファイルがサーバーに残らない」という意味で、トランスクリプトも要約もクラウド
- 完全ローカルを実現しているのは Meetily / Vibe（OSS・英語圏製）と MacWhisper（Mac専用）
- 日本勢（Rimo / toruno / Otolio）はすべてクラウドで、訴求は「国内データセンター」「AI学習なし」止まり
- **toruno は Mac版を提供していない**と公式に明記しており、クロスプラットフォームも差別化要素になる

**訴求文言として使える具体的な差分**【推】:
「議事録の内容が一度もインターネットに出ない」は、クラウド勢が構造的に言えない。
人事面談・法務・医療・官公庁・研究・M&A といった「そもそも外部に出せない会議」が想定顧客になる。
これらの層は現状、録音を諦めるか手書きメモで運用しており、既存製品では代替できていない。

### 6-2. AGPL-3.0 の制約

**Microsoft Store**: **配布可能**【確】。
現行の Microsoft Store ポリシー 7.19（2025-09-10発行、2025-10-14発効）を確認したところ、
**GPL/AGPL を名指しで禁じる条項は存在しない**。価格に関する条項は 10.8.7 の
「Not be priced irrationally high relative to the features and functionality provided by your product」のみで、
2022年に議論された「オープンソースソフトウェアから利益を得ようとしてはならない」という条項は**現行版には入っていない**
（[Microsoft Store Policies 7.19](https://learn.microsoft.com/en-us/windows/apps/publish/store-policies)）。
またMicrosoftの開発者契約は「if you include FOSS, your license terms may conflict with the limitations set forth in Section 3 of those Terms, but only to the extent required by the FOSS that you use」として
FOSSライセンスの優先を明示的に許容している（[jbkempf.com](https://jbkempf.com/blog/Windows-Store-and-the-GPL/)）。
既に `STORE_SUBMISSION.md` が有料・買い切り前提で書かれており、**この方針は継続できる**。

**Mac App Store**: **実質不可**【確】。
GPL/AGPL は Apple の App Store 利用規約（特にコード署名を含むDRM的制約と5デバイス制限）と衝突するとFSFが指摘しており、
GNU Go の事例では Apple が App Store から削除して解決している
（[FSF: More about the App Store GPL Enforcement](https://www.fsf.org/blogs/licensing/more-about-the-app-store-gpl-enforcement)）。
**ただしこれは実務上ほぼ問題にならない**。本調査で確認した限り、
Granola / MacWhisper / superwhisper / Otter / Fathom / Limitless / Audio Hijack / Loopback は
**全社が Mac App Store 外の Developer ID 直販**であり【確】、
既に `MAC_RELEASE.md` が「Mac App Store distribution is a separate track」として直販DMGを正としている。**現行方針のままでよい**。

**AGPL の「ネットワークサービス」条項について**【推】:
本アプリは 127.0.0.1 でのみ待ち受けるローカルバックエンドであり、第三者にネットワーク越しにサービス提供していない。
したがって AGPL 13条のソース提供義務は、改変版を**配布**する場合にのみ発生する通常のGPLと同じ扱いになる。
ただしこれは法的助言ではなく、有料販売と組み合わせる際は弁護士確認を推奨する。

### 6-3. 収益化の選択肢

| 方式 | 適合性 | 論点 |
|---|---|---|
| **買い切り（Microsoft Store）** | 現行方針。継続可 | AGPLでも Store ポリシー上の障害なし【確】。ただし**ソースが公開されている以上、自前ビルドできる人は買わない**。「ビルド済み・署名済み・サポート付き」への対価という位置づけになる |
| **GitHub Sponsors** | 現行。継続 | 会議機能で利用者が増えれば効く。ただし単独では収益として弱い【推】 |
| 直販（macOS DMG） | 可能 | Gumroad等。MacWhisper が €59 買い切りで成立させている先行例がある |
| サブスク | **非推奨**【推】 | STORE_SUBMISSION.md が「買い切りのみのサブスクなし」を製品名に入れており、これ自体が差別化になっている。競合が全社サブスクなので崩すべきでない |
| 企業向けサポート契約 | **最有望**【推】 | 「外部に出せない会議」を持つ組織は導入支援・オンプレ検証・監査対応にコストを払う。AGPLは**むしろ有利**（監査可能性が売りになる） |

**推奨**【推】: 買い切り＋Sponsors は現行のまま維持し、
会議機能の完成後に**「監査可能な完全ローカル議事録ツール」として法人向けの導入支援を有償で提供する**線を足す。
AGPLでソースが公開されていることは、この層に対しては欠点ではなく**セキュリティ監査を通せる根拠**になる。

---

## 7. リスクと未確認事項

### 7-1. 実装前に潰すべき最優先事項

1. **kotoba-whisper-v2.0 の日本語精度・RTF を対象ノートPCで実測する**【最優先】。
   公称CERは信頼できるが、実機のRTFとメモリ使用量が未確認。ここが全設計の前提になる。
   なお **large-v3-turbo の日本語品質は未検証**で、turbo はデコーダ層を32→4に削減しており
   OpenAI公式が「低リソース言語では精度が落ちる」と明記しているため、日本語主体の本件で無条件に推すのは危険【確】。
2. **macOS の権限フローを実機で確認する**。署名・公証済みビルドで
   `NSMicrophoneUsageDescription` / `NSAudioCaptureUsageDescription` が正しくプロンプトを出すか。
   CIランナー（macos-26）では Apple Intelligence 同様に検証できない可能性が高い。
3. **Electron 42 で `getDisplayMedia` ＋ `audio:'loopback'` が Windows/macOS 双方で実際に音を拾うか**の最小PoC。
   ここが動かなければ Phase 2 の前提が崩れる。

### 7-2. 出典が弱い・未確認の事項

| 項目 | 状態 |
|---|---|
| Notta の月額価格（¥1,980 / ¥4,180） | 三次情報のみ。公式ページはJSタブで取得できず |
| MacWhisper の価格・機能 | 一次情報に到達できずレビューサイトのみ |
| tl;dv の価格 | 競合ブログ経由 |
| Google Meet の 2026-03-25 ボット制限 | **tl;dv（競合ベンダー）のブログのみが出典。Google公式の裏取りが必要** |
| Anarlog のライセンス | サイト側「GPL」言及 vs GitHub「MIT」で**矛盾** |
| AI GIJIROKU のサービス継続 | 旧ドメインが無関係コンテンツ、alt.ai製品ページは404 |
| Apple SpeechTranscriber が Apple Intelligence 有効化を要するか | 公式に明記なし。実機確認が必要 |
| Nemotron 3.5 Streaming の CPU 実測RTF | **「日本語×真ストリーミング×商用可」の唯一候補だがCPU動作が完全に未確認** |
| MSIXパッケージでの WASAPI ループバックに関する Microsoft 公式明言 | 状況証拠は強いが一次資料なし |
| Core Audio Taps が App Sandbox / Mac App Store で使用可という Apple 公式資料 | 見つからず |
| gated HFモデルの重みを自社インストーラに再パッケージすることのHF利用規約適合性 | **法務確認ポイント** |
| ビデオ会議中のCPU%・温度・バッテリー消費の定量レポート | 定性報告のみ存在。**自社実測すればPR材料になる**【推】 |

### 7-3. 製品リスク

1. **「録れているつもりで無音」**【確】。macOSは権限なしで無音の生きたストリームが返り警告も出ない。
   Windowsは音が鳴っていないとデータが来ない。**レベル監視と録音中の可視インジケータが必須**。
   会議1時間分を失うのは、この製品カテゴリで最も致命的な失敗。
2. **端末が重くなる**【確】。i5-8250U級では large が RTF 2.05 で破綻する。
   会議アプリのビデオエンコードと帯域を奪い合うため、**スレッド数を物理コアの1/4〜1/2に絞り、モデルを1段落とす**設計にすべき。
   低スペック機ではリアルタイム表示を自動オフにするフォールバックが要る。
3. **法的・倫理的な録音同意**【推】。会議録音は参加者の同意が前提。
   本製品は録音者の端末で完結するため事業者としての責任は限定されるが、
   UI上に「参加者の同意を得てください」という明示は入れるべき。競合も同様の表示を行っている。
4. **スコープの膨張**。Phase 1〜4 を一括で企画すると 20〜33人日になる。
   前述の推奨順（kotoba-whisper差し替え → Phase 1 → 会議要約テンプレ → Phase 2 → Phase 3）で、
   各段階が単独で出荷可能な形に刻むこと。

---

## 8. 参考: 本書で確認した既存コードの事実

| 事実 | 確認方法 |
|---|---|
| faster-whisper 1.2.1 の `transcribe()` は `np.ndarray` を受け付ける | `.venv` の `faster_whisper/transcribe.py` を直接確認 |
| Silero VAD v6 (ONNX) が faster-whisper に同梱済み | `faster_whisper/assets/silero_vad_v6.onnx` の存在を確認 |
| PyAV / ctranslate2 / onnxruntime が PyInstaller で同梱済み | `desktop/backend.spec` |
| Electron は 42.4.0（loopback要件の39+を満たす） | `desktop/package.json` |
| `entitlements.mac.plist` にマイク権限が**ない** | ファイル全文確認（allow-jit / allow-unsigned-executable-memory / disable-library-validation のみ） |
| UIは `http://127.0.0.1:PORT` から配信される | `desktop/main.js` の `mainWindow.loadURL(backendUrl)` |
| Swiftヘルパーの subprocess＋JSON パターンが実装済み | `app/apple_intelligence.py` / `desktop/apple-intelligence-helper/main.swift` |
| CIランナーは `macos-26`（Xcode 26 = macOS 26 SDK） | `docs/CLOUD-MAC-BUILD.md` |
| 現行のモデル選択は RAM 16GB未満で base/tiny | `app/system_info.py` の `select_model_for_memory()` |

---

## 追補: タスクバー常駐とステータスの可視化（2026-07-29 オーナー指示）

> 原文要旨: 会議中にも動かすのであれば、**タスクバーに常駐させて、アプリの画面を開いていなくても動いているのがすぐ分かる**ようにしてほしい。

### なぜ必須要件なのか

会議中の録音は**アプリ画面を見ていない状態が既定**になる。ユーザーはZoomやTeamsの画面を見ており、Local Transcriberはバックグラウンドにいる。この状態で最も起きてはいけない失敗は次の2つ。

1. **録れているつもりで録れていない**（開始し忘れ・デバイス切替で無音・権限拒否）。会議は再現できないので取り返しがつかない
2. **止めたつもりで録り続けている**（会議後の雑談や別件の通話まで録音される。**プライバシー事故に直結**し、完全ローカルを謳う製品としては致命的）

したがって常駐表示は装飾ではなく、**製品の信頼性そのもの**として扱う。

### 設計要件（Phase 1から入れる）

- **トレイ常駐アイコンの状態表示**: 停止中／録音中／一時停止／文字起こし処理中／エラー、を**アイコンの見た目だけで判別できる**こと（色だけに頼らず形も変える。色覚多様性への配慮）
- **録音中であることの継続的な提示**: 録音中はアイコンをアニメーションさせるか、**経過時間をツールチップに出す**。Windowsはタスクバーのオーバーレイアイコン、macOSはメニューバーの常時表示が使える
- **トレイメニューから最小操作が完結**: 開始／停止／一時停止／保存先を開く／直近の文字起こしを開く。**アプリ画面を開かずに止められる**ことが重要（上記の失敗2の対策）
- **無音・入力断の検知と通知**: 一定時間レベルがゼロなら「音が入っていません」を通知する。**録れていない事故を会議中に気づける**ようにする（失敗1の対策）
- **終了時の確認**: アプリを閉じようとしたとき録音中なら警告する。誤終了で会議の記録を失わない
- **リソース表示**: リアルタイム文字起こしを走らせるとCPU負荷が上がるため、トレイのツールチップに簡易な負荷表示を出す案（本体調査で「会議中の実測がない」ことが未確認事項として挙がっているため、まず自分で測れる形にする意味もある）

### 実装上の注意

- Electronの `Tray` APIで両OS対応可能。**macOSはテンプレート画像**（`Tray.setImage` に `@2x` とテンプレート指定）を使わないとダークモードで潰れる
- **自動起動（ログイン時常駐）は既定オフ**にする。完全ローカルを謳う製品が勝手に常駐すると不信につながるため、ユーザーが明示的に有効化する設計にする
- 録音中の表示は**OS側の録音インジケータ（macOSのマイク使用中表示など）と二重になる**が、それでよい。むしろ一致していることが安心材料になる

### Phase配置の変更

この要件はPhase 1（オフライン録音ボタン＋録音後文字起こし）に**同時に入れる**。理由は、録音機能を出した時点で「開いていないと不安」という体験になり、後付けでは信頼を損なった後の回復になるため。工数はPhase 1の3〜5人日に**1〜2人日を追加**する見積り（推測）。
