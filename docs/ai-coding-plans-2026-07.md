# AIコーディングサービス比較・プラン見直しメモ(2026-07-24調査)

Claude / Codex / Gemini / Grok / Kimi の5サービスを調査し、現在の契約プランを見直した記録。

## 現在の契約状況と結論

| サービス | 現在 | 結論 |
|---|---|---|
| Claude | Max(**週次上限に到達**) | 維持。5xなら20xへの増額検討+他ツールへのオフロード |
| Codex | Plus($20) | 維持(ChatGPT本体も利用しているため) |
| Gemini | AI Pro($19.99) | **維持**(AI ProでAntigravity CLIが利用可能) |
| Grok | 未契約 | 契約不要。GitHub Copilot Free(無料)で試せる |
| Kimi | 未契約 | 必須ではないが、Claude天井対策としてModerato($15プロモ)の試験導入に価値あり |

※ 2026-07-26追記: 無料・極安の追加候補(DeepSeek / GLM / MiniMax と各種無料枠)は本ドキュメント後半の「追記: 無料・極安の選択肢」を参照。

---

## 5社比較(2026年7月時点)

| | Claude (Anthropic) | Codex (OpenAI) | Gemini (Google) | Grok (xAI) | Kimi (Moonshot) |
|---|---|---|---|---|---|
| 主力モデル | Fable 5 / Opus 4.8 | GPT-5.6系 (Sol/Terra/Luna) | Gemini 3.1 Pro | Grok 4.5 / grok-code-fast-1 | K3(最大1Mコンテキスト) |
| CLIエージェント | Claude Code | Codex CLI | Antigravity CLI(`agy`、Gemini CLIの後継) | Grok Build(2026年5月ベータ) | Kimi Code |
| 個人プラン | Pro $20 / Max $100 / Max $200 | Plus $20 / Pro $100 / Pro $200 | AI Plus $7.99 / AI Pro $19.99 / AI Ultra $99.99(新Ultraは$100) | Lite $10 / SuperGrok $30 / Heavy $300 | Adagio 無料 / Moderato $19 / Allegretto $39 / Allegro $99 / Vivace $199 |
| 強み | 長時間の自律エージェント実行、エコシステムの成熟度 | Plusが安価、モデル多様性の確保 | Deep Research、Veo、Google連携 | 速度とコスト、Claude Code互換のSkills | 低価格でのCLIエージェント提供 |
| 注意点 | 5時間枠+週次上限(全モデル用とSonnet用の2本) | 5時間枠+週次上限の二重キャップ | Gemini CLI(旧)は消費者プランから利用不可に | Buildはまだベータ、エコシステムが若い | 料金体系の再編を予告中 |

---

## 各サービス詳細

### Claude Max — 週次上限への対策

上限は2系統ある: **5時間ローリング枠**と**週次上限**(全モデル用+Sonnet専用の2本)。今回問題なのは**週次上限**。

対策(効果順):

1. **Max 5x($100)ならMax 20x($200)へ増額** — セッション/週次とも枠が拡大(Pro比5倍→20倍)。
2. **軽いタスクを他ツールにオフロード** — 定型修正・調査・コミットメッセージ等をCodex / Kimi Code / Grokに逃がし、Claudeの枠を重いエージェントタスクに温存する。今回Grok/Kimiを検討する主目的はこれ。
3. **モデル使い分け** — 週次上限は全モデル用とSonnet用が別枠。軽作業をSonnetに寄せるとOpus系の枠を温存できる。
4. 補足: 週次上限50%増のプロモーションが2026年8月19日まで延長中(恒久対策にはならない)。
5. あふれた分の恒久対策は**API従量課金への切り替え**のみ(個人プランに超過分の追加購入はない)。

### Codex Plus

- $20でGPT-5.6系のCodexが利用可能。5時間ローリング枠+週次上限の二重キャップ(週次は5時間枠のリセットでは回復しない)。
- 上限到達時はクレジット追加購入が可能(約4セント/クレジット)。
- 2026年4月9日にOpenAIがプラン再編: 旧$200 Proが $100 / $200 の2段階に。

### Gemini AI Pro と Antigravity CLI

- **Gemini CLI(旧)は2026年6月18日以降、個人GoogleログインがAntigravity CLIへ移行**。消費者プランでのGemini CLI利用は終了方向。
- **後継のAntigravity CLI(`agy`)はAPIキー不要のGoogle OAuthログインで、AI Pro / AI Ultraのプラン枠で利用できる** → AI Pro契約の価値は継続。
- Antigravity CLIは2026年5月19日(Google I/O 2026)発表、Go製。新AI Ultraプラン($100)はAntigravity利用上限がAI Proの5倍。
- 注意: プロンプトのサポート言語は英語(日本語も動くが業務利用は英語推奨)、AIクレジットは日本未提供(2026年5月時点)。

### Grok

- **grok-code-fast-1**: 314B MoE、256Kコンテキスト、SWE-Bench Verified 約70.8%。API価格 $0.20/$1.50 per 1M tokens(キャッシュ入力$0.02)。
- **GitHub Copilot経由で利用可能**。Copilotはローカルリポジトリ(GitHub未ホストでも)で動作し、必要なのはGitHubアカウントのみ。
  - **Copilot Free(無料)**: 月2,000コード補完+50チャット。grok-code-fast-1は2026年3月からFreeの自動モデル選択(Auto)に含まれる。
  - 本格利用はxAI APIまたはOpenRouterの従量課金が現実的。
- **Grok Build**(2026年5月ベータ): xAIのCLIエージェント。最大8並列サブエージェント。SuperGrok($30/月)で利用可能。Grok Skills/ConnectorsはClaude Codeのskills・plugins・CLAUDE.mdと互換を謳う。
- **Grok 4.5**(2026年7月8日): 約1.5Tパラメータの上位モデル。EUは7月中旬提供予定。

### Kimi / Kimi Code

- **Kimi Code**: K3モデル(最大1Mコンテキスト)搭載のCLI/IDEエージェント。`curl -fsSL https://code.kimi.com/kimi-code/install.sh | bash` でインストール。
- プラン: **Adagio(無料)→ Moderato $19(現在$15プロモ)→ Allegretto $39 → Allegro $99 → Vivace $199**。
  - Moderato: K3が256Kコンテキストまで
  - Allegretto以上: 1Mコンテキスト+高速アクセス
- Kimi Codeのクレジットはサブスクに含まれる(APIはプラン外)。K3のAPIは$3/$15 per 1M(キャッシュで入力$0.30まで低減)。
- 注意: 「一般会員特典とKimi Code特典を分離する新料金体系」を公式が予告しており、近く料金構成が変わる可能性。

---

## 追記: 無料・極安の選択肢(2026-07-26調査)

Claudeの週次上限オフロード先として、DeepSeekと中国系の格安コーディングプラン、無料枠を追加調査した。**結論: 追加コストゼロの枠(Antigravity CLI)を先に使い切り、次にDeepSeekの従量課金をClaude Codeへ挿す。定額の安心が欲しければGLM Coding Plan Lite。**

### 追加コストゼロで使える枠

| 手段 | 内容 | 備考 |
|---|---|---|
| **Antigravity CLI(`agy`)** | 契約中のGemini AI Pro($19.99)の枠内 | **すでに支払い済み。最優先のオフロード先** |
| GitHub Copilot Free | 月2,000コード補完+50チャット、Autoにgrok-code-fast-1を含む | GitHubアカウントのみで可 |
| Cerebras 無料枠 | GPT-OSS 120Bを1日14,400リクエスト | 高速。OpenCode / Clineから利用 |
| OpenRouter `:free` モデル | Qwen系、gemini-2.0-flash-exp(1Mコンテキスト)など | `:free`は20種以上あるが実用は8モデル程度 |
| DeepSeek 新規登録 | API 500万トークン無料 | 品質確認の試用に十分 |
| Kimi Adagio | 無料ティア | K3はModerato以上でないと使えない |

### DeepSeek — 従量課金での最安手

- 定額サブスクは存在せず**純粋な従量課金**。月額固定費ゼロで使った分だけ。
- **V4 Flash: $0.14/$0.28 per 1M tokens**(1Mコンテキスト) / **V4 Pro: $0.435/$0.87**(恒久75%値下げ後)。
- **`api.deepseek.com/anthropic` のAnthropic互換エンドポイントが公式提供**されており、環境変数の設定だけでClaude Code本体をそのままDeepSeekで動かせる。CLIを覚え直す必要がない。

```sh
export ANTHROPIC_BASE_URL=https://api.deepseek.com/anthropic
export ANTHROPIC_AUTH_TOKEN=<YOUR_DEEPSEEK_API_KEY>
export ANTHROPIC_API_KEY=<YOUR_DEEPSEEK_API_KEY>
export CLAUDE_CODE_DISABLE_NONSTREAMING_FALLBACK=1
```

- モデルIDはV4系で `deepseek-v4-pro[1m]` 等(`deepseek-chat` は旧ID)。V4 Proをmain/default、V4 FlashをHaiku相当・サブエージェントへ割り当てる構成が公式ドキュメントの推奨。
- 注意: Anthropic公式サポートの構成ではない(DeepSeek側がドキュメント化し、Anthropicが黙認している状態)。

### 定額の格安コーディングプラン

| プラン | 最安ティア | 上限の目安 | Claude Code対応 |
|---|---|---|---|
| **GLM(Z.ai)** | **Lite $18/月**(年払い等の割引で**$12.60/月**) | 約80プロンプト/5時間、400/週 | ◎ Anthropic互換で公式サポート |
| **MiniMax** | **Starter $10/月** / Plus $20 / Max $50 | Starter 約100プロンプト/5時間 | ◎(20以上のツールに対応) |
| Kimi | Moderato $19($15プロモ) | K3は256Kコンテキストまで | ◎ |
| Qwen | $50/月 | 約6,000リクエスト/5時間、9万/月 | ○ ただし割高 |

- **GLMが価格対性能で最も評価が高い**。全ティアでGLM-5.2 / GLM-5-Turbo / GLM-4.7 / GLM-4.5-Airが使え、Claude Code・Cline・OpenCodeへのドロップインをZ.aiが公式に案内している。上位はPro $72 / Max $160。割引は月払い10%・四半期20%・年払い30%。
- MiniMax Starter $10が名目最安。ただし**トークン枠がコーディング以外(画像・音声・動画)と共用**のため、マルチモーダル併用で想定より早く枯れる。
- **Qwen Codeの無料OAuth枠は2026年4月15日で終了**(1,000→100リクエスト/日と段階的に削減後、廃止)。CLI自体はOSSのままなので、自前APIキー運用なら選択肢に残る。
- 比較サイトごとにGLMの価格表記が$10/$30/$80と$18/$72/$160で割れている。**$18が現行の定価**で、前者は割引後またはプロモ時点の数字と見られる。契約前にz.aiの公式ページで要確認。

### 推奨アクション(効果順)

1. **Antigravity CLIを使い倒す** — 追加費用ゼロ。契約済みのAI Pro枠。
2. **DeepSeekの従量課金をClaude Codeに挿す** — 軽いタスクを全部逃がしても月数ドル規模に収まる見込み。まず無料500万トークンで品質を確認。
3. それでも定額の安心が欲しければ **GLM Coding Plan Lite(年払い$12.60/月)** — Kimi Moderato $19より安く、Claude Code互換性も同等以上。

### 注意: データ送信先

DeepSeek / Kimi / GLM / MiniMaxはいずれも中国系サービスで、**コードとプロンプトが国外サーバーへ送信される**。業務リポジトリで使う場合はデータ取扱いポリシーと社内規程の確認が必須。個人の検証用途なら問題ないが、業務利用はAntigravity CLI / Copilot Free側に寄せるほうが安全。

---

## 主な情報源

- Claude: [Claude Code Usage Limits (Morph)](https://www.morphllm.com/claude-code-usage-limits) / [週次上限プロモ延長 (Help Net Security)](https://www.helpnetsecurity.com/2026/07/13/claude-code-weekly-limits-promotion-extended/)
- Codex: [Codex Pricing (Morph)](https://www.morphllm.com/codex-pricing) / [Codex Usage Limits解説](https://knightli.com/en/2026/04/15/codex-usage-limits-five-hour-weekly-credits/)
- Gemini: [Antigravity CLI移行 (note)](https://note.com/sunwood_ai_labs/n/n135ffa38aef2) / [Antigravity CLIとは (AI総合研究所)](https://www.ai-souken.com/article/what-is-antigravity-cli) / [Antigravity 2.0 (BigGo)](https://finance.biggo.jp/news/202605211851_Google_Antigravity_2.0_Launch_New_AI_Ultra_Plan)
- Grok: [grok-code-fast-1公式](https://x.ai/news/grok-code-fast-1) / [Copilot Free対応 (GitHub Changelog)](https://github.blog/changelog/2026-03-04-grok-code-fast-1-is-now-available-in-copilot-free-auto-model-selection/) / [xAI Dev Stack 2026 (Codersera)](https://codersera.com/blog/xai-grok-build-skills-connectors-guide-2026/)
- Kimi: [Kimi K3料金(公式)](https://www.kimi.com/ja-jp/resources/kimi-k3-pricing) / [Kimi Code with K3 (Digital Applied)](https://www.digitalapplied.com/blog/kimi-code-k3-hands-on-setup-plans-cache-2026) / [料金ヘルプ(公式)](https://www.kimi.com/ja/help/membership/membership-pricing) / [Kimi Code Plans and Pricing (CodeAgentSwarm)](https://www.codeagentswarm.com/en/guides/kimi-code-plans-and-pricing)

追記調査(2026-07-26)分:

- DeepSeek: [DeepSeek Pricing 2026 (FelloAI)](https://felloai.com/deepseek-pricing/) / [V4 Pro Pricing Guide (DeepInfra)](https://deepinfra.com/blog/deepseek-v4-pro-pricing-guide-2026-providers-cost-analysis) / [Claude Code公式ANTHROPIC_BASE_URL設定 (TheRouter)](https://therouter.ai/news/deepseek-awesome-agent-claude-code-copilot-opencode-routing/) / [How to Use DeepSeek V4 in Claude Code (Verdent)](https://www.verdent.ai/guides/deepseek-v4-in-claude-code)
- GLM: [GLM Coding Plan Pricing (AI Pricing Guru)](https://www.aipricing.guru/z-ai-subscription-pricing/) / [$18 GLM Coding Plan 価値分析 (Digital Applied)](https://www.digitalapplied.com/blog/glm-coding-plan-worth-it-2026-value-analysis) / [Z.AI Pricing & Tiers (Layer3Labs)](https://www.layer3labs.io/guides/glm-coding-plan-explained)
- MiniMax: [MiniMax Pricing 2026 (FelloAI)](https://felloai.com/minimax-pricing/) / [M2.5 Pricing (Verdent)](https://www.verdent.ai/guides/minimax-m2-5-pricing)
- Qwen: [無料枠終了の経緯 (InventiveHQ)](https://inventivehq.com/blog/qwen-code-still-free-2026-shutdown) / [Qwen OAuth Free Tier Policy Adjustment (GitHub Issue #3203)](https://github.com/QwenLM/qwen-code/issues/3203)
- 横断比較・無料枠: [AI Coding Plan Comparison 2026 (coding-plan.org)](https://coding-plan.org/en/) / [無料LLM API一覧@10社以上 (note)](https://note.com/gadget_hack/n/nd391c04bc338) / [OpenRouter無料モデル8選 (Qiita)](https://qiita.com/locallab/items/3dbfadf579a3a480c78a)
