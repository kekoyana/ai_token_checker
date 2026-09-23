# Copilot CLIの使用量と残量APIの不一致

2026-09-23の調査では、表示の精度不足に加え、Copilot CLIの応答とアカウント残量APIで異なる利用枠が返る事象を確認しました。

## 確認した事実

- 残量API（`GET https://api.github.com/copilot_internal/user`）はAI Credits方式を返しました。`copilot_plan` は `individual_pro`、`access_type_sku` は `plus_monthly_subscriber_quota` でした。
- 14:21と14:27（JST）の応答で、月次枠は7,000 credits、残量は5,824.6 creditsのままでした。APIの `percent_remaining` は83.2です。計算すると83.20857…%になります。
- APIの応答時刻と `timestamp_utc` は進んでいました。`Cache-Control` は `private, max-age=60, s-maxage=60` でした。本ツールはローカルキャッシュを使用していません。
- 同日のCLIセッションログには、Chat枠200、消費200、残量0%の `quotaSnapshots` が記録されていました。14:25〜14:26（JST）には `HTTP 402 / You have exceeded your monthly quota` が発生しています。
- 直近の `gpt-5.4-nano` 呼び出しには `total_nano_aiu: 0` とChat枠の消費が併記されていました。ただしセッション全体の `totalNanoAiu` は0ではありません。CLIでの全処理が無料だったとは判断できません。
- 利用者に確認したCLIの `/user show` と、`gh auth status` のアカウントは一致しました。CLIのバージョンは1.0.87でした。

したがって、割合の丸めだけで今回の症状を説明することはできません。アカウント残量APIの月次クレジット枠と、CLIのモデル呼び出しで返るChat枠が一致していません。CLIの認証・契約情報の保持、呼び出し経路ごとの利用枠、GitHub側の集計など、どこで相違が生じたかは未確定です。応答時刻が新しくても、使用量の集計が最新である証拠にはなりません。

## 本ツールで修正した点

- AI Credits方式を判別し、`Premium requests` ではなく `AI credits` と表示。
- 整数の `remaining` や丸め済みの割合より、小数付きの `quota_remaining` を優先。
- 割合は小数2桁、`EST. LEFT` は残量 / 月次枠をクレジット単位で表示。
- SKUからPro+を判別。ゼロ容量のダミー枠を「残量100%」として扱わない。
- JSONにAPIスナップショット時刻を含める。

これらは表示の改善であり、GitHub側の利用枠の不一致を解消するものではありません。

## 次の切り分け

1. 作業を区切ってCopilot CLIを再起動し、必要なら `/login` で認証を更新する。
2. 同一アカウントでCLIの `/usage`、GitHubの利用状況画面、本ツールの `--service copilot --json` を比較する。`/usage` はセッションの使用量であり、月次残量とは区別する。
3. Pro+のクレジットが残っているのにChat枠超過が続く場合は、GitHub Supportへ発生時刻とRequest IDを提示する。今回の例は `D6A3:2DA4BB:17A80B2:1C17CD7:6AB36313`（2026-09-23 14:26 JST）。認証トークンや会話全文を添付する必要はありません。

参考: [課金方式](https://docs.github.com/en/copilot/concepts/billing-and-usage/individuals/billing)、[CLIコマンド](https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference)、[認証のトラブルシューティング](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/troubleshoot-copilot-cli-auth)。
