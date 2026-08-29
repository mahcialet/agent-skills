# 互換性

## 仕様確認（2026-08-30）

| 対象 | 確認した内容 | 参照 |
|---|---|---|
| Codex | `SKILL.md`の`name`/`description`、`.agents/skills`、`agents/openai.yaml`、`allow_implicit_invocation: false` | [OpenAI Docs](https://developers.openai.com/codex/skills/) |
| Copilot CLI | `.agents/skills`、小文字hyphen名、`/skills list`・`info`・`reload`、Skill内追加ファイル | [GitHub Docs](https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-skills) |
| GitHub CLI | `skills/*/SKILL.md`、Codex/Copilot target、SHA pin、`publish --dry-run` | [gh manual](https://cli.github.com/manual/gh_skill) |

共通 `skills/reader-first-editor/SKILL.md` をsource of truthとし、provider別の
手書きコピーは置かない。Codex固有の `agents/openai.yaml` にはUIと起動ポリシー
だけを置く。

## ローカル検証状況

- GitHub CLI 2.97.0: `gh skill install --help` と
  `gh skill publish --help` で上記機能を確認。
- `gh skill publish --dry-run`: CIと完了監査で実行する。
- Codex CLI: この作業環境に実行ファイルがなく、一覧・明示起動の実機検証は未実施。
- Copilot CLI: この作業環境に実行ファイルがなく、一覧・明示起動および
  `agents/openai.yaml` の無害性の実機検証は未実施。

実行ファイルが利用可能になったら、次を確認して結果とversionを追記する。

1. CodexでSkill一覧と `$reader-first-editor`、暗黙起動禁止、review非破壊性。
2. Copilot CLIで `/skills list`、`/skills info reader-first-editor`、
   `/reader-first-editor`、review非破壊性。
3. Copilotが `agents/openai.yaml` を含むディレクトリを問題なく読み込むこと。

## 既知の制約・未決事項

- `gh skill` はpublic previewであるため、手動配置手順を維持する。
- Copilotには、確認済み資料上でCodexの
  `allow_implicit_invocation: false` と同等の静的設定がない。portable本文で
  reviewを既定にし、ファイル変更には明示依頼を要求する。
- Skillが二つになる前に、repo-wide tagとSkill接頭辞付きtagのどちらを使うか
  `release-policy.md` で決定する。
- 実文コーパスは未整備。初版は合成fixtureであり、匿名化可能な実例を継続追加する。
- 自動日本語構文解析器は導入せず、数値はtripwireだけに使う。
