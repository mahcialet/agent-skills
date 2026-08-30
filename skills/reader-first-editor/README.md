# Reader-First Editor

`reader-first-editor` は、人間向けの日本語・英語文章を、校正、初読理解、読み返し
リスク、情報階層、意味保存の観点でreviewまたは改稿するSkillです。明示的に依頼
された場合は、文書のclaimを同一リポジトリ内のcode、設定、test、他文書などと
照合します。

既定は非破壊のreviewです。改稿には明示的な依頼が必要で、改稿前後を意味台帳で
比較します。不明な期限、担当、手順、保証、義務を創作しません。

## 対象

- README、設計書、技術解説、runbook
- PR説明、review、Issue、社内依頼、メール
- 公告、FAQ、UIテキスト、エラー説明、意思決定記録
- 文法上は正しいが、過密・平板・反復的・曖昧な文章
- READMEと設定のdefault値、runbookと現行CLI、複数文書間の条件などの整合確認

創作、詩、広告voice、厳密なControlled Language適合、コードや識別子そのものの
書き換えは対象外です。一般的な外部fact checkingや、外部URLの内容を無制限に
取得・検証する用途にも使いません。

## 明示起動

- Codex: `$reader-first-editor この文章をレビューしてください: ...`
- Copilot CLI: `/reader-first-editor この文章をレビューしてください: ...`

改稿が必要なら `revise-safe`、`diff`、`authoring` などを指定してください。
[出力モード](references/core/output-modes.md)に契約を記載しています。

## リポジトリ内の証拠に基づく校閲

`repository-review` はread-onlyです。対象文書と関連するリポジトリ内の証拠を
照合し、文書も証拠fileも変更せず結果を返します。

Codex:

```text
$reader-first-editor docs/configuration.mdをrepository-reviewで確認してください。
```

Copilot CLI:

```text
/reader-first-editor README.mdのdefault値がcodeと一致するかrepository-reviewしてください。
```

判定には次の5状態を使います。

| 状態 | 意味 |
|---|---|
| `VERIFIED` | リポジトリ内の具体的な証拠がclaimを支持する |
| `CONTRADICTED` | リポジトリ内の具体的な証拠がclaimと明確に矛盾する |
| `SUPPORTED-BY-CITATION` | 外部citationの存在を確認したが、外部内容は未検証 |
| `UNSUPPORTED` | 確認scope内にrepository内証拠もcitationも見つからない |
| `UNVERIFIED` | 外部情報が必要で、通常のrepository-reviewでは確認できない |

根拠が見つからないことを、claimが誤っている証拠にはしません。code、test、設定、
文書が競合する場合も、一律の優先順位でどれかを正しいと決めず、source-of-truth宣言や
位置付けを確認して競合を報告します。モデルの知識は検証済み証拠として使いません。
外部serviceの現在の提供状況など、真偽に外部の最新情報が必要なclaimは
`UNVERIFIED` とします。このようなclaimは、citationがないだけで `UNSUPPORTED` へ
変えません。

探索は対象文書の参照、識別子、設定キーから始め、関連する範囲へ段階的に広げます。
大規模リポジトリを黙って全件走査しません。Git履歴は履歴依存のclaim、明示依頼、
証拠競合の文脈確認に限定します。詳細は
[リポジトリ内の証拠に基づく校閲](references/core/repository-grounded-review.md)を
参照してください。

出力例:

- [日本語のrepository-review例](examples/repository-review-ja.md)
- [英語文書のrepository-review例](examples/repository-review-en.md)

校閲後の改稿も必要な場合は、`repository-review` と `revise-safe` などの改稿モードを
両方明示してください。校閲結果を先に確定し、意味保存gateを通してから改稿します。

## ローカルコーパス育成（planned）

実文、review履歴、採用・却下判断を、インストール済みSkillとは別のlocal dataへ蓄積し、
corpusとruleの候補を保守的に評価するworkflowを設計しています。この機能はまだ未実装で、
現在の通常reviewやbundled evalには影響しません。

設計上は、候補の収集、corpusへのpromotion、behavior-changing ruleのpromotionを別のgateに
分けます。収集したcandidateやpromoted local corpusを通常reviewへ暗黙に読み込まず、
明示的なapplyと人間の承認なしに `SKILL.md`、references、evalsを変更しません。

- [コーパス運用](docs/corpus-workflow.md)
- [コーパスデータモデル](docs/corpus-data-model.md)
- [ルール昇格](docs/rule-promotion.md)
- [Agentによる調査](docs/agent-investigation.md)
- [日本語構文解析](docs/syntax-analysis.md)
- [ライセンスとプライバシー](docs/licensing-and-privacy.md)

## Portability

CodexとGitHub Copilotで同じ `SKILL.md` をsource of truthにします。
`agents/openai.yaml` は任意のCodex metadataと暗黙起動禁止だけを持ち、これがなくても
portable instructionsは完結します。

This is an independent, unofficial implementation. It does not reproduce the
ISO 24495-1 standard and does not claim ISO conformance or certification. See
[NOTICE.md](NOTICE.md) for sources and licenses.
