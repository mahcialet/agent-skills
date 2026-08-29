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
  `gh skill publish --help` で上記機能を確認。`publish --dry-run` と、ローカル
  sourceから一時ディレクトリへのcopy installに成功した。
- Codex CLI 0.151.0: Nodeの一時実行で検証。project scopeの `.agents/skills` から
  `$reader-first-editor` を明示起動し、Skill本文、必須core、日本語技法を読み込んで
  `review` を返した。read-only sandboxで原文・ファイルは変更されなかった。
  Skill名を含めない同種の依頼ではSkillファイルを読み込まなかったため、
  `allow_implicit_invocation: false` も実行trace上で確認した。
- GitHub Copilot CLI 1.0.81: Nodeの一時実行で検証。`copilot skill list` がproject
  scopeの `reader-first-editor` を表示し、`agents/openai.yaml` の同梱は検出を
  阻害しなかった。`/reader-first-editor` の明示起動は書込み・shell toolを禁止した
  非対話セッションでreviewを返した。

実機検証は一時repoで行い、user scopeやこのリポジトリの作業ツリーへSkillを
インストールしていない。host versionが変わった場合は、同じ項目を再検証する。

## 既知の制約・未決事項

- `gh skill` はpublic previewであるため、手動配置手順を維持する。
- Copilotには、確認済み資料上でCodexの
  `allow_implicit_invocation: false` と同等の静的設定がない。portable本文で
  reviewを既定にし、ファイル変更には明示依頼を要求する。
- Skillが二つになる前に、repo-wide tagとSkill接頭辞付きtagのどちらを使うか
  `release-policy.md` で決定する。
- 実文コーパスは未整備。初版は合成fixtureであり、匿名化可能な実例を継続追加する。
- 自動日本語構文解析器は導入せず、数値はtripwireだけに使う。
