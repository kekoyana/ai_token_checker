# AI Usage Check

Codex、Claude Code、GitHub Copilot、Antigravity CLI (`agy`)、Grok Build (`grok`) の残り使用量を1つの表にまとめるmacOS/Linux向けCLIです。認証トークンは標準出力にもファイルにも保存しません。

## セットアップ

本体はPython 3.9以上で動作します。agyの取得だけは、現行CLIのローカル接続に対応する補助CLI（Node.js 18以上）を一度導入します。

```sh
chmod +x usage_check.py
npm install -g antigravity-usage
```

Antigravity IDEが起動中なら、補助CLIがローカル接続から使用枠を取得します。CLI版のagyだけを使う場合は、補助CLIにも一度ログインしてください。

```sh
antigravity-usage login
```

Grokは Grok Build CLI (`@xai-official/grok`) のログイン情報（`~/.grok/auth.json`）をそのまま利用します。未ログインなら一度ログインしてください。

```sh
grok login
```

GitHub CopilotはGitHub CLIのログイン情報を利用します。未ログインなら一度ログインしてください。

```sh
gh auth login
```

補助CLIやGrok CLIがなくてもCodex、Claude Code、GitHub Copilotのチェックは動作します。

このディレクトリの外から `ai-usage` として使う場合:

```sh
uv tool install .
ai-usage
```

直接実行する場合:

```sh
./usage_check.py
./usage_check.py --json
./usage_check.py --service codex --service claude
./usage_check.py --service copilot
./usage_check.py --service grok
```

## 取得方法

- Codex: `codex app-server` の公式 `account/rateLimits/read` API
- Claude Code: Claude CodeのローカルOAuth認証を使う使用量API
  - 5時間枠・7日枠に加え、応答の `limits` 配列にあるモデル別の週間枠（`7日 Fable` など）も1行ずつ表示します。Fable 5.1のような上位モデルは全体の7日枠とは別に専用の週間枠を持つため、この行で残量とリセット時刻を確認できます。
- GitHub Copilot: GitHub CLIの認証を使い、GitHubの内部利用枠APIから月次のAI Credits（旧課金方式ではPremium requests）、Chat、Completionsを取得
  - AI Credits方式では小数付き残量を優先し、割合は小数2桁、`EST. LEFT` は実残量 / 月次枠（`cr`）を表示します。Pro+はAPIの契約SKUで判別します。
  - 無制限の枠は表示せず、上限がある枠だけを表示します。このAPIは非公開仕様のため、GitHub側の変更で利用できなくなる可能性があります。
- agy: `antigravity-usage quota --json`（Antigravity IDEへのローカル接続、または補助CLI独自のOAuth認証）
  - Gemini系モデルはすべて同一のクォータ枠（共通プール）を共有するため、「Gemini (共通枠)」として1行に集約して表示します（Gemini 3.8 Flashなど新モデルが追加されても自動で集約されます）。残量APIが数値を返さない場合はREMAINは「不明」となります。
- Grok: Grok Build CLIのOAuth認証（`~/.grok/auth.json`）で課金APIと契約APIを参照。アクセストークンが期限切れならリフレッシュトークンで自動更新します（更新後のトークンはメモリ上のみで、ファイルへは書き戻しません）

未ログインやCLI未導入のサービスはERROR行になり、取得できた他サービスはそのまま表示されます。長いエラーメッセージは表内では末尾を省略し、表の下の「エラー詳細」に全文を出します。

残量が少ない枠は色で警告します（残り25%以下=黄、10%以下=赤）。消費ペースの警告（`やや速い` / `枯渇懸念` / `枯渇寸前`）は残量とは別の軸なのでPACE列だけを塗ります。色は端末に出力するときだけ付き、`--color never` や環境変数 `NO_COLOR` で無効化、`--color always` でパイプ時にも強制できます。Claude CodeをAPIキー課金で利用している場合、サブスクリプションの残量枠は返りません。

Grokは課金APIが使用枠を返さないプラン（X Basicなどの無料枠）だと、プランだけ取得できて `取得済み（表示可能な枠なし）` になります。使用枠が表示されるのは、クレジット枠を持つSuperGrok系プランで Grok Build を利用している場合です。トークンは環境変数 `GROK_ACCESS_TOKEN`（または `XAI_ACCESS_TOKEN`）でも渡せます。

agyが `Individual quota reached` で止まる場合、`Resets in ...` の残り時間は**残量ではありません**。枯渇して初めて実際の期限が表示されるため、「62時間ある」は「62時間使えない」という意味です。Gemini系は約3日、Claude系は5時間と枠ごとに周期が異なります。詳細は [docs/antigravity-quota-behavior.md](docs/antigravity-quota-behavior.md)。

Claude行が `APIエラー HTTP 429` になる場合は、使用量エンドポイントのレート枠（アカウント単位・スライディング型）に達しています。**触るほど解けにくくなる**ため、約1時間放置してから1回だけ再実行してください。詳細は [docs/claude-429-rate-limit.md](docs/claude-429-rate-limit.md)。

Copilot CLIを使っても割合が変わらない場合、`EST. LEFT` のクレジット残量を確認してください。APIの `percent_remaining` は小数1桁に丸められており、7,000 creditsの枠では0.1%が7 creditsに相当します。本ツールはAI Credits方式の `quota_remaining` から割合を計算し、微小な消費を実残量でも確認できるようにしています。毎回APIへ問い合わせますが、GitHub側のキャッシュや集計の反映までは保証できません。`--json` の `snapshot_at` はAPI応答のスナップショット時刻で、最後に使用量が集計された時刻とは限りません。なお、本ツールはGitHub CLIのアカウントを参照するため、Copilot CLIで利用中のアカウントと同じか確認してください。現行の課金方式は [GitHubの公式説明](https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/billing) を参照してください。

Copilotの月次クレジットが残っていても、CLI側で別のChat枠が消費され、HTTP 402になる事象も確認しています。表示精度の修正だけでは解消しません。調査結果と切り分け手順は [docs/copilot-quota-mismatch.md](docs/copilot-quota-mismatch.md)。

`USED` と `REMAIN` はAPIの割合、またはAPIの実残量から計算した割合です。`PACE` はウィンドウの経過時間と使用率から、現在のペースでリセットまで持つかを推定します。Claudeの `EST. LEFT` はAnthropic公表のプラン別目安から、5時間枠を推定プロンプト数の中央値、週間枠をSonnet 1時間＝2pt・Opus 1時間＝10ptとして共通ポイントへ換算します。公表目安のないモデル別枠（`7日 Fable` など）はプラン容量からの汎用換算になるため、他のClaude行より粗い参考値です。他サービスのポイントと概算順位も仮の容量配点による参考値で、実際のタスク内容によって大きく外れる可能性があります。

APIからプランを取得できない場合は、Git管理されない `.usage_check.local.json` で指定できます。

```json
{
  "plans": {
    "agy": "AI Pro"
  }
}
```

## 認証情報とGit管理

このツールは各CLIのローカル認証情報を読み取ってAPIへ渡しますが、トークン自体を標準出力やリポジトリ内へ保存しません。`--json` の出力にもトークンは含まれません。

`.gitignore` では環境変数ファイル、認証ファイル、秘密鍵、使用量キャッシュ、Python生成物を除外しています。認証ファイルをプロジェクト内へコピーしないでください。特に以下はGitへ追加しないでください。

- `.env` とその派生ファイル
- OAuthトークン、APIキー、秘密鍵
- `~/.claude/`、`~/.codex/`、`~/.gemini/`、`~/.grok/`、GitHub CLI内の認証ファイル
- `~/Library/Application Support/antigravity-usage/` 内のファイル
