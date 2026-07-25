# AI Usage Check

Codex、Claude Code、Antigravity CLI (`agy`)、Grok Build (`grok`) の残り使用量を1つの表にまとめるmacOS/Linux向けCLIです。認証トークンは標準出力にもファイルにも保存しません。

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

補助CLIやGrok CLIがなくてもCodexとClaude Codeのチェックは動作します。

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
./usage_check.py --service grok
```

## 取得方法

- Codex: `codex app-server` の公式 `account/rateLimits/read` API
- Claude Code: Claude CodeのローカルOAuth認証を使う使用量API
- agy: `antigravity-usage quota --json`（Antigravity IDEへのローカル接続、または補助CLI独自のOAuth認証）
- Grok: Grok Build CLIのOAuth認証（`~/.grok/auth.json`）で課金APIと契約APIを参照。アクセストークンが期限切れならリフレッシュトークンで自動更新します（更新後のトークンはメモリ上のみで、ファイルへは書き戻しません）

未ログインやCLI未導入のサービスはERROR行になり、取得できた他サービスはそのまま表示されます。Claude CodeをAPIキー課金で利用している場合、サブスクリプションの残量枠は返りません。

Grokは課金APIが使用枠を返さないプラン（X Basicなどの無料枠）だと、プランだけ取得できて `取得済み（表示可能な枠なし）` になります。使用枠が表示されるのは、クレジット枠を持つSuperGrok系プランで Grok Build を利用している場合です。トークンは環境変数 `GROK_ACCESS_TOKEN`（または `XAI_ACCESS_TOKEN`）でも渡せます。

Claude行が `APIエラー HTTP 429` になる場合は、使用量エンドポイントのレート枠（アカウント単位・スライディング型）に達しています。**触るほど解けにくくなる**ため、約1時間放置してから1回だけ再実行してください。詳細は [docs/claude-429-rate-limit.md](docs/claude-429-rate-limit.md)。

`USED` と `REMAIN` はAPIから取得した実際の割合です。`PACE` はウィンドウの経過時間と使用率から、現在のペースでリセットまで持つかを推定します。Claudeの `EST. LEFT` はAnthropic公表のプラン別目安から、5時間枠を推定プロンプト数の中央値、週間枠をSonnet 1時間＝2pt・Opus 1時間＝10ptとして共通ポイントへ換算します。他サービスのポイントと概算順位も仮の容量配点による参考値で、実際のタスク内容によって大きく外れる可能性があります。

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
- `~/.claude/`、`~/.codex/`、`~/.gemini/`、`~/.grok/` 内のファイル
- `~/Library/Application Support/antigravity-usage/` 内のファイル
