# Reader-First Editor

`reader-first-editor` は、人間向けの日本語・英語文章を校正・校閲・改稿するSkillです。
文法や表記に加え、初読で理解できるか、どこで読み返しが生じるか、情報の関係や
優先順位が伝わるかを確認します。改稿では、元の内容が保たれているかも確かめます。
リポジトリ内校閲を明示された場合は、文書のclaimを同一リポジトリ内のcode、設定、test、
他文書などと照合します。

既定は、原文を変更しない `review` です。改稿には明示的な依頼が必要です。改稿する場合は、
事実、誰が何をするか、条件、例外、否定、必須・推奨・任意・可能性の違い、用語などが
変わっていないかを、改稿前後で確認します。不明な期限、担当、手順、保証、義務は
創作しません。確認項目の詳細は
[改稿前後の確認項目](references/core/semantic-preservation.md)を参照してください。

## 主要機能

| 機能 | 内容 | モードと変更範囲 |
|---|---|---|
| 校正・文章レビュー | 文法、表記、用語に加え、複数の意味に読める箇所、読み返しが必要になる箇所、情報の関係や優先順位を確認する | `review`。既定値であり、原文やファイルを変更しない |
| 内容を変えない改稿 | 事実、条件、例外、必須・推奨・任意・可能性の違い、コード、コマンド、設定値、識別子などを保ちながら、並べ替え・分割・結合・明確化を行う | `revise-safe`。明示依頼が必要 |
| リポジトリ内校閲 | 文書のclaimを、同じリポジトリのcode、設定、test、他文書と照合する | `repository-review`。read-only |
| 構造変更の提案 | 情報の移動、重複の統合、削除候補と、失われる可能性のある内容を示す | `revise-structural`。明示的な削除許可がなければ提案だけを返す |
| 変更点の比較 | 改稿前後の文章に、変更理由と内容が変わるリスクを対応付ける | `diff`。明示依頼が必要 |
| 草案作成 | 既知情報から文章を作り、不明な期限・担当などは `TODO` やplaceholderで示す | `authoring`。明示依頼が必要 |
| 日本語の表記統一 | 句読点、漢字・仮名、全半角、記号、単位、表記揺れだけを整える | `jtf-only`。内容や構造は変更しない |

`review` では、問題、読者への影響、改善方針を報告します。校正で見つかった問題を本文へ
反映する場合は、`revise-safe` などの改稿モードも指定してください。各モードの正確な契約は
[出力モード](references/core/output-modes.md)に記載しています。

## 起動例

Codexでは `$reader-first-editor`、Copilot CLIでは `/reader-first-editor` を使って
明示起動します。

```text
# 校正・文章レビュー。原文は変更しない
$reader-first-editor README.mdを校正し、重要な問題を報告してください。

# 内容を変えずに改稿する
$reader-first-editor docs/guide.mdをrevise-safeで改稿してください。

# リポジトリ内の証拠と照合する
$reader-first-editor docs/configuration.mdをrepository-reviewで確認してください。

# 日本語の表記だけを整える
$reader-first-editor announcement.mdをjtf-onlyで整えてください。
```

Copilot CLIでは、上記の `$reader-first-editor` を `/reader-first-editor` に置き換えます。

## 対象と対象外

- README、設計書、技術解説、runbook
- PR説明、review、Issue、社内依頼、メール
- 公告、FAQ、UIテキスト、エラー説明、意思決定記録
- 文法上は正しいが、過密・平板・反復的・曖昧な文章
- READMEと設定のdefault値、runbookと現行CLI、複数文書間の条件などの整合確認

創作、詩、広告voice、厳密なControlled Language適合、コードや識別子そのものの
書き換えは対象外です。一般的な外部fact checkingや、外部URLの内容を無制限に
取得・検証する用途にも使いません。

## 校閲：リポジトリ内の証拠との照合

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
両方明示してください。校閲結果を先に確定してから改稿し、元の内容との食い違いが
ないかを改稿後にも確認します。

## 育成・評価機能（一部implemented）

以下の機能は、通常の校正・校閲・改稿から分離されています。local corpusや構造sensorを
通常reviewへ暗黙に読み込んだり、自動起動したりしません。

### ローカルコーパスを育成する

実文、review履歴、採用・却下判断を、インストール済みSkillとは別のlocal dataへ蓄積し、
corpusとruleの候補を保守的に評価するworkflowを整備しています。public promotionと
通常reviewからのlocal corpus利用は未実装であり、現在の通常reviewには影響しません。

#### 現在の実装範囲

schema v1、local data directoryの解決、state transition、audit log、manual corpus CLI、
local promotion、public GitHub PRのreference-only収集、adversarial investigation bundle、
proposal draftは実装済みです。provider-neutralなregression plan・result取込み・report、
人間の承認artifact、限定したrule applyも実装済みです。

設計上は、候補の収集、corpusへのpromotion、behavior-changing ruleのpromotionを別々の
確認段階に分けます。収集したcandidateやpromoted local corpusを通常reviewへ暗黙に読み込まず、
明示的なapplyと人間の承認なしに `SKILL.md`、references、evalsを変更しません。

#### local corpusを操作する

manual CLIの例:

```bash
tool=skills/reader-first-editor/scripts/corpus_tool.py
data_dir=/path/to/reader-first-editor-data

python3 "$tool" --data-dir "$data_dir" corpus list
python3 "$tool" --data-dir "$data_dir" corpus collect \
  --record candidate.json --actor reviewer --reason "local candidate"
python3 "$tool" --data-dir "$data_dir" corpus annotate <candidate-id> \
  --annotation annotation.json --actor reviewer --reason "annotation confirmed"
python3 "$tool" --data-dir "$data_dir" corpus accept <candidate-id> \
  --actor reviewer --reason "regression sampleとして採用"
python3 "$tool" --data-dir "$data_dir" corpus promote <candidate-id>
python3 "$tool" --data-dir "$data_dir" corpus promote <candidate-id> --apply \
  --actor reviewer --reason "local corpusへ昇格"
```

最後の二つは、最初がread-only preview、`--apply` 付きがlocal dataだけへの書込みです。
どちらもcore ruleやbundled evalを変更しません。project scopeを使う場合は、projectの
`.gitignore` に `.reader-first-editor/` を追加してください。

#### public GitHub PRから収集する

public GitHub PRを収集する例:

```bash
python3 "$tool" --data-dir "$data_dir" corpus collect-github \
  --repository digital-go-jp/design-tokens --pr-number 138 \
  --language ja --translation-status native --genre technical-readme \
  --reader-description "design tokenを利用する開発者・デザイナー" \
  --actor reviewer --reason "reference-only candidate" --dry-run
```

`collect-github` は明示実行時だけnetworkへ接続します。既定でpublic repositoryだけを対象にし、
PR本文、patch、review/comment本文を保存しません。変更済みMarkdownのpath・SHA、review state、
inline threadの位置と件数だけを `github_evidence` に残し、rightsは `unknown`、textは
`reference-only`、recordは `local_only` とします。`--dry-run` を外すまでlocal dataへも
書き込みません。

#### ruleを調査・昇格する

rule investigationは、support／control recordを明示指定して `rules bundle` を実行した場合だけ
開始します。bundleはCounterexample Hunterを最優先にし、既定判断を `HOLD` とします。
`rules validate-investigation` は未説明の反例、固定閾値だけ、頻度だけ、既存ruleのduplicateを
含む `PROMOTE` を拒否します。`rules propose --apply` もlocal proposalを保存するだけで、core rule、
references、evalsを変更しません。詳細は[Agentによる調査](docs/agent-investigation.md)を参照して
ください。

proposal後は `rules regression-plan`、`rules regression-ingest`、`rules regression-report` で、
bundled eval全件、promoted corpus、proposal evalをCodexとGitHub Copilotの結果から集約します。
Python tool自体はproviderを起動しません。pass reportは `rules approve` で人間が別artifactとして
承認し、`rules apply` は既定preview、`--apply` 付きで承認済みのexact diffだけを適用します。
apply対象はSkill本文・references・evalsに限定され、validator失敗時はrollbackします。toolは
commitもpushもしません。詳しくは[ルール昇格](docs/rule-promotion.md)を参照してください。

### 日本語構造sensorを評価する

日本語構造sensorはoptionalです。`scripts/analyze_ja.py analyze` を明示実行した場合だけGiNZAを
読み込み、dependency未導入やparse失敗では非致命のavailability resultを返します。通常reviewから
install、model download、解析を自動実行しません。出力は構造観測値であり、可読性やRR labelの
ground truthではありません。

`ab-report` は同じcaseのLLM-onlyとLLM-plus-signalsをCodex／GitHub Copilot間で比較します。
回帰、provider差拡大、改善なしを `do-not-default` とし、改善が観測されても人間の確認なしに
既定利用を有効化しません。install pin、schema、CLI例は[日本語構文解析](docs/syntax-analysis.md)を
参照してください。

関連文書:

- [コーパス運用](docs/corpus-workflow.md)
- [コーパスデータモデル](docs/corpus-data-model.md)
- [ルール昇格](docs/rule-promotion.md)
- [Agentによる調査](docs/agent-investigation.md)
- [日本語構文解析](docs/syntax-analysis.md)
- [ライセンスとプライバシー](docs/licensing-and-privacy.md)

## ポータビリティ

CodexとGitHub Copilotで同じ `SKILL.md` をsource of truthにします。
`agents/openai.yaml` は任意のCodex metadataと暗黙起動禁止だけを持ち、これがなくても
portable instructionsは完結します。

This is an independent, unofficial implementation. It does not reproduce the
ISO 24495-1 standard and does not claim ISO conformance or certification. See
[NOTICE.md](NOTICE.md) for sources and licenses.
