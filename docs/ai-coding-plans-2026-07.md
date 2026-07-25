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

## 主な情報源

- Claude: [Claude Code Usage Limits (Morph)](https://www.morphllm.com/claude-code-usage-limits) / [週次上限プロモ延長 (Help Net Security)](https://www.helpnetsecurity.com/2026/07/13/claude-code-weekly-limits-promotion-extended/)
- Codex: [Codex Pricing (Morph)](https://www.morphllm.com/codex-pricing) / [Codex Usage Limits解説](https://knightli.com/en/2026/04/15/codex-usage-limits-five-hour-weekly-credits/)
- Gemini: [Antigravity CLI移行 (note)](https://note.com/sunwood_ai_labs/n/n135ffa38aef2) / [Antigravity CLIとは (AI総合研究所)](https://www.ai-souken.com/article/what-is-antigravity-cli) / [Antigravity 2.0 (BigGo)](https://finance.biggo.jp/news/202605211851_Google_Antigravity_2.0_Launch_New_AI_Ultra_Plan)
- Grok: [grok-code-fast-1公式](https://x.ai/news/grok-code-fast-1) / [Copilot Free対応 (GitHub Changelog)](https://github.blog/changelog/2026-03-04-grok-code-fast-1-is-now-available-in-copilot-free-auto-model-selection/) / [xAI Dev Stack 2026 (Codersera)](https://codersera.com/blog/xai-grok-build-skills-connectors-guide-2026/)
- Kimi: [Kimi K3料金(公式)](https://www.kimi.com/ja-jp/resources/kimi-k3-pricing) / [Kimi Code with K3 (Digital Applied)](https://www.digitalapplied.com/blog/kimi-code-k3-hands-on-setup-plans-cache-2026) / [料金ヘルプ(公式)](https://www.kimi.com/ja/help/membership/membership-pricing)
