# Reader-First Editor

`reader-first-editor` は、人間向けの日本語・英語文章を、初読理解、読み返しリスク、
情報階層、意味保存の観点でreviewまたは改稿するSkillです。

既定は非破壊のreviewです。改稿には明示的な依頼が必要で、改稿前後を意味台帳で
比較します。不明な期限、担当、手順、保証、義務を創作しません。

## 対象

- README、設計書、技術解説、runbook
- PR説明、review、Issue、社内依頼、メール
- 公告、FAQ、UIテキスト、エラー説明、意思決定記録
- 文法上は正しいが、過密・平板・反復的・曖昧な文章

創作、詩、広告voice、厳密なControlled Language適合、コードや識別子そのものの
書き換えは対象外です。

## 明示起動

- Codex: `$reader-first-editor この文章をレビューしてください: ...`
- Copilot CLI: `/reader-first-editor この文章をレビューしてください: ...`

改稿が必要なら `revise-safe`、`diff`、`authoring` などを指定してください。
[出力モード](references/core/output-modes.md)に契約を記載しています。

## Portability

CodexとGitHub Copilotで同じ `SKILL.md` をsource of truthにします。
`agents/openai.yaml` は任意のCodex metadataと暗黙起動禁止だけを持ち、これがなくても
portable instructionsは完結します。

This is an independent, unofficial implementation. It does not reproduce the
ISO 24495-1 standard and does not claim ISO conformance or certification. See
[NOTICE.md](NOTICE.md) for sources and licenses.
