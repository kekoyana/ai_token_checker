# AI Usage Check

Codex、Claude Code、Antigravity CLI (`agy`) の残り使用量を1つの表にまとめるmacOS/Linux向けCLIです。認証トークンは標準出力にもファイルにも保存しません。

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

補助CLIがなくてもCodexとClaude Codeのチェックは動作します。

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
```

## 取得方法

- Codex: `codex app-server` の公式 `account/rateLimits/read` API
- Claude Code: Claude CodeのローカルOAuth認証を使う使用量API
- agy: `antigravity-usage quota --json`（Antigravity IDEへのローカル接続、または補助CLI独自のOAuth認証）

未ログインやCLI未導入のサービスはERROR行になり、取得できた他サービスはそのまま表示されます。Claude CodeをAPIキー課金で利用している場合、サブスクリプションの残量枠は返りません。

## 認証情報とGit管理

このツールは各CLIのローカル認証情報を読み取ってAPIへ渡しますが、トークン自体を標準出力やリポジトリ内へ保存しません。`--json` の出力にもトークンは含まれません。

`.gitignore` では環境変数ファイル、認証ファイル、秘密鍵、使用量キャッシュ、Python生成物を除外しています。認証ファイルをプロジェクト内へコピーしないでください。特に以下はGitへ追加しないでください。

- `.env` とその派生ファイル
- OAuthトークン、APIキー、秘密鍵
- `~/.claude/`、`~/.codex/`、`~/.gemini/` 内のファイル
- `~/Library/Application Support/antigravity-usage/` 内のファイル
