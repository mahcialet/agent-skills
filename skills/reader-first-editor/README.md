# Reader-First Editor

`reader-first-editor` は、人間向けの日本語・英語の文章を校正・校閲・改稿するSkillです。
誤字や表記に加え、要点を初読でつかめるか、条件・例外や情報同士の関係を読み返さずに
理解できるか、重要な情報と補足の優先順位が分かるかを確認します。

長文では確認範囲をcoverageとして示します。また、同じ役割を持つ要素群から外れる少数例も、
根拠とともに確認します。改稿では、元の内容が変わっていないことも確かめます。
リポジトリ内校閲を明示された場合は、文書の記述を同一リポジトリ内のコード、設定、テスト、
他文書などと照合します。

既定は、原文を変更しない `review` です。改稿には明示的な依頼が必要です。
改稿前後では、事実、誰が何をするか、条件、例外、否定、必須・推奨・任意・可能性の違い、
用語などが変わっていないかを確認します。不明な期限、担当、手順、保証、義務は創作しません。
確認項目の詳細は
[改稿前後の確認項目](references/core/semantic-preservation.md)を参照してください。

## 主要機能

| 機能 | 内容 | モードと変更範囲 |
|---|---|---|
| 校正・校閲 | 文法、表記、用語に加え、複数の意味に読める箇所、読み返さないと条件・例外が分からない箇所、要点と補足の優先順位を確認する | `review`。既定値であり、原文やファイルを変更しない |
| 内容を変えない改稿 | 事実、条件、例外、必須・推奨・任意・可能性の違い、コード、コマンド、設定値、識別子などを保ちながら、並べ替え・分割・結合・明確化を行う | `revise-safe`。明示依頼が必要 |
| リポジトリ内校閲 | 文書の記述を、同じリポジトリのコード、設定、テスト、他文書と照合する | `repository-review`。文書や証拠ファイルを変更しない |
| 長文coverage | 見出しなどの構造単位で局所確認した後、文書全体を確認し、0件と未確認を区別する | 長文・複数file・網羅性を求められた `review`／`repository-review`。原文やファイルを変更しない |
| 局所整合性 | 同じ役割を持つ要素群の型・値・表記から外れる少数例をcandidateとして拾い、意図的な例外か確認する | `review` は与えられた本文とcontext内、`repository-review` は関連するrepository evidenceまで確認。少数派だけで誤りとせず、自動修正しない |
| 構造変更の提案 | 情報の移動、重複の統合、削除候補と、失われる可能性のある内容を示す | `revise-structural`。明示的な削除許可がなければ提案だけを返す |
| 変更点の比較 | 改稿前後の文章に、変更理由と内容が変わるリスクを対応付ける | `diff`。明示依頼が必要 |
| 草案作成 | 既知情報から文章を作り、不明な期限・担当などは `TODO` や確認事項として示す | `authoring`。明示依頼が必要 |
| 日本語の表記統一 | 句読点、漢字・仮名、全半角、記号、単位、表記揺れだけを整える | `jtf-only`。内容や構造は変更しない |

`review` では、問題、読者への影響、改善方針を報告します。校正・校閲で見つかった問題を本文へ
反映する場合は、`revise-safe` などの改稿モードも指定してください。各モードの正確な契約は
[出力モード](references/core/output-modes.md)に記載しています。

具体例:

- [関係を一語で済ませた文の確認例](examples/relationship-clarity-ja.md)
- [長文のcoverage-driven review例](examples/coverage-review-ja.md)
- [DB定義の局所整合性review例](examples/local-consistency-ja.md)

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

# 長い文書を構造単位で確認し、coverageを示す
$reader-first-editor docs/operations.mdを見落としがないようreviewし、coverageも示してください。

# DB定義の同じ役割の列から外れる少数例と根拠を確認する
$reader-first-editor docs/database.mdのaudit timestampをrepository-reviewしてください。

# 日本語の表記だけを整える
$reader-first-editor announcement.mdをjtf-onlyで整えてください。
```

Copilot CLIでは、上記の `$reader-first-editor` を `/reader-first-editor` に置き換えます。

## 対象と対象外

次のような文章を対象にできます。

- README、設計書、技術解説、runbook
- PR説明、レビュー、Issue、社内依頼、メール
- 公告、FAQ、UIテキスト、エラー説明、意思決定記録
- 文法上は正しいが、過密・平板・反復的・曖昧な文章
- READMEと設定に書かれた既定値、runbookと現行CLI、複数文書間の条件などの整合確認

創作、詩、広告voice、厳密なControlled Language適合、コードや識別子そのものの
書き換えは対象外です。リポジトリ外の事実を広く検証したり、外部URLの内容を
無制限に取得・検証したりする用途にも使いません。

## 校閲：リポジトリ内の証拠との照合

`repository-review` は読み取り専用です。対象文書と関連するリポジトリ内の証拠を
照合し、文書も証拠ファイルも変更せず結果を返します。

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
| `VERIFIED` | リポジトリ内の具体的な証拠が文書の記述を支持する |
| `CONTRADICTED` | リポジトリ内の具体的な証拠が文書の記述と明確に矛盾する |
| `SUPPORTED-BY-CITATION` | 外部の引用・参照（citation）はあるが、その内容は未検証 |
| `UNSUPPORTED` | 確認範囲内に、リポジトリ内の証拠もcitationも見つからない |
| `UNVERIFIED` | 外部情報が必要で、通常のrepository-reviewでは確認できない |

根拠が見つからないだけでは、文書の記述が誤っている証拠にはなりません。コード、テスト、
設定、文書が競合する場合も、一律の優先順位でどれかを正しいとは決めません。どの資料を
優先するか、各資料をどの用途で使うかがリポジトリ内で明示されているかを確認し、競合を
報告します。

モデルの知識は、検証済みの証拠として使いません。外部サービスの現在の提供状況など、
真偽の確認にリポジトリ外の最新情報が必要な記述は `UNVERIFIED` とします。このような記述は、
citationがないだけで `UNSUPPORTED` へ変えません。

探索は対象文書の参照、識別子、設定キーから始め、関連する範囲へ段階的に広げます。
大規模リポジトリを黙って全件走査しません。Git履歴の確認は、履歴に依存する文書の記述、
明示依頼、証拠が競合する文脈の確認に限定します。詳細は
[リポジトリ内の証拠に基づく校閲](references/core/repository-grounded-review.md)を
参照してください。

### 長文と局所整合性

長文では、見出し、段落群、表、list、code fenceをinventory化します。構造単位ごとに
局所passを行った後、文書全体のglobal passを行います。前半で数件見つけても探索を止めず、
severityはcandidate収集後に付けます。coverage summaryでは `checked`、`partial`、
`not-checked` を使い、確認済み0件と未確認を区別します。詳細は
[coverage-driven reviewの設計](docs/coverage-driven-review.md)を参照してください。

DB定義表などでは、semantic peer groupを先に定義します。その上で、type、nullable、default、
constraintなどの分布から、少数値をcandidateとして確認できます。全体頻度や少数派だけでは
誤りとしません。通常の `review` は与えられた本文とcontext内で確認し、`repository-review`
または明示的な根拠確認ではrepository内のschema、migration、comment、code、test、ADRなどから
例外理由を探します。結果は
`EXPLAINED`、`UNEXPLAINED`、`CONTRADICTED`、`NOT-AN-OUTLIER` に分け、
`UNEXPLAINED` を誤りや自動修正の根拠にしません。

補助ツールとして、次の処理を実装しています。Markdownの構造inventory、coverage reportの
schema・整合性検証、
関係候補語の全出現scan、Markdown DB定義表の構造化、明示peer group内の少数値scanです。coverage
reportの作成・検証には作成元inventoryと元Markdownを渡します。toolは元Markdownから正規inventoryを
再生成し、本文hash、全inventory field、source、全chunk、必須観点、pass順序を照合します。
reportは `review`／`repository-review` のmodeを保持し、後者では `repository-consistency` を必須にします。
空または空白のみのMarkdownはinventory段階で拒否します。
coverage workflow artifactはschema v2です。旧v1は元Markdownから再生成します。
DB scannerは1件以上のpeer groupを要求し、member不足を `partial` として返します。
schema-backed artifactでは、booleanの `true` をversion 1として受理しません。
CSV、DDL、ORM schemaの構造化parserは未実装です。未対応形式やtool失敗の場合も
LLM-only確認を続け、coverageを `partial` として未確認範囲を示します。

Markdown inventoryが構造として認識するのは、`#` 形式のH1〜H3、pipe table、fenced code block、list markerと
indentされた継続行からなるlistです。H4〜H6とindentのないlazy continuationはparagraphとして
扱われ、現行toolはそれだけを理由に `partial` にしません。これらを含む文書では、inventoryの
`complete` をCommonMark全構造の認識完了と解釈せず、周辺contextを別途確認します。

出力例:

- [日本語のrepository-review例](examples/repository-review-ja.md)
- [英語文書のrepository-review例](examples/repository-review-en.md)

校閲後の改稿も必要な場合は、`repository-review` と `revise-safe` などの改稿モードを
両方明示してください。校閲結果を先に確定してから改稿し、元の内容との食い違いが
ないかを改稿後にも確認します。

<a id="育成評価機能一部implemented"></a>

## 開発者向け：Skillの育成・評価（一部implemented）

以下は、Skillを育成・評価する開発者向けの機能です。通常の校正・校閲・改稿からは
分離されています。local corpusや構造sensorを通常のreviewへ暗黙に読み込んだり、
自動起動したりしません。校正・校閲・改稿だけを利用する場合、この節のCLI操作は不要です。

### ローカルコーパスを育成する

実文、review履歴、採用・却下判断を、インストール済みSkillとは別のlocal dataへ蓄積できます。
蓄積した候補は、tool外で人間が確認してからcorpusへ追加し、ruleの候補として慎重に評価します。
toolはactorやreviewerが人間かを認証しません。
public promotionと通常のreviewでのlocal corpus利用は未実装であり、現在の通常reviewには
影響しません。

#### 現在の実装範囲

実装済みの範囲は、schema v1、local data directoryの解決、state transition、audit log、
manual corpus CLI、local promotion、public GitHub PRのreference-only収集、
adversarial investigation bundle、proposal draftです。さらに、provider-neutralな
regression plan・result取込み・report、caller-supplied approval artifact、限定したrule applyも
利用できます。人間によるreviewはtool外の運用要件です。

候補の収集、corpusへのpromotion、behavior-changing ruleのpromotionは、別々の確認段階に
分けています。収集したcandidateやpromoted local corpusを通常のreviewへ暗黙に読み込みません。
また、明示的なapplyとapproval artifactなしに `SKILL.md`、references、evalsを変更しません。

#### local corpusを操作する

manual CLIの例:

manual collectionはtoken、secret、credential、個人情報を自動検出・redactしません。raw textを
含むrecordは、保存前に内容を確認してください。`corpus collect --dry-run` はschema・rights制約と
保存先を確認しますが、redaction previewは生成しません。
manual／local-file recordの `source.immutable_revision` と `text.content_hash` はcaller-suppliedです。
validatorは必要な型・形式・record内の関係を確認しますが、外部sourceやembedded contentからhashを
再計算しないため、利用者が値と実体の一致を確認します。

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

最後の2コマンドは、書き込みの有無が異なります。前者は書き込まずpreviewだけを返し、
後者は `--apply` によりlocal dataだけへ書き込みます。どちらもcore ruleやbundled evalを
変更しません。project scopeを使う場合は、projectの `.gitignore` に
`.reader-first-editor/` を追加してください。

#### public GitHub PRから収集する

public GitHub PRを収集する例:

```bash
python3 "$tool" --data-dir "$data_dir" corpus collect-github \
  --repository digital-go-jp/design-tokens --pr-number 138 \
  --language ja --translation-status native --genre technical-readme \
  --reader-description "design tokenを利用する開発者・デザイナー" \
  --actor reviewer --reason "reference-only candidate" --dry-run
```

`collect-github` は、明示実行時だけnetworkへ接続します。既定ではpublic repositoryだけを
対象とし、PR本文、patch、review/comment本文は保存しません。変更fileのうち `.md` または
`.markdown` で、statusが `removed` ではないfileをcandidateにします。

保存するmetadataは、変更済みMarkdownのpath・SHA、review state、inline threadの位置と件数を
中心に、repositoryのvisibility・license、PRのstate・draft・時刻・base／head／merge SHA、fileの
status・previous path・change count、review ID・時刻・本文有無なども含みます。
thread集約はlive responseまたはfixtureの `review_comments` でparent commentがreplyより先に並ぶことを
前提とし、順序の正規化は行いません。
これらを `github_evidence` に残し、rightsは `unknown`、textは `reference-only`、recordは
`local_only` とします。repository licenseの値と、GitHub REST APIのrepository metadataから
観測したことは `rights.notes` に記録します。`--dry-run` を外すまでlocal dataへも書き込みません。

#### ruleを調査・昇格する

rule investigationは、support／control recordを明示して `rules bundle` を実行した場合だけ
開始します。bundleではCounterexample Hunterを最優先にし、既定判断を `HOLD` とします。
`rules validate-investigation` は、選択済みcontrolが `explained` またはboundaryへ記載されているかと、
`unexplained` が空かを検証します。説明内容の妥当性は自然言語から判定しません。固定閾値だけの根拠、
頻度だけの根拠、既存ruleのduplicateは、Agent resultが申告したstructured flagを検証して
`PROMOTE` を拒否します。toolは自然言語からflagの正しさを推論しないため、自己申告、本文、
counterexample説明の整合は人間が確認します。`rules propose --apply` もlocal proposalを保存するだけで、
core rule、references、evalsを変更しません。
boundary pairではfieldが空でないこととcontrolの記載漏れを確認しますが、`fires` がsupport recordか、
両IDが実在するか、意味上のminimal pairかは確認しません。また、`rules propose` の作成時には
positive／negative／boundary間のeval ID重複を拒否せず、後段の `regression-plan` と `rules apply` が
拒否します。
詳細は[Agentによる調査](docs/agent-investigation.md)を参照してください。

proposal後は `rules regression-plan`、`rules regression-ingest`、`rules regression-report` を
使います。既定の `--eval-dir` ではbundled eval全件、`--corpus-record` で選んだpromoted record、
proposal evalを対象に、CodexとGitHub Copilotの結果を集約します。`--eval-dir` を明示すると、その
directoryへ置き換わり、Skillのbundled eval directoryか、全suiteを含むかは検証しません。
promoted record全件は自動選択しません。Python tool自体はproviderを起動しません。

pass reportでは、`rules approve` がcaller-suppliedなreviewerと理由を別artifactへ記録します。
toolはreviewerが人間かを認証しないため、人間による明示reviewはtool外で行います。`rules apply` は
既定でpreviewを返し、`--apply` を付けた場合だけ承認artifactと一致するexact diffを適用します。
previewではpatch適用後のeval suiteの `cases` を解析し、新規caseのIDとfixture内容がregression planへ
固定したproposal evalに一致することを確認します。metadataにIDがあるだけでは通過しません。
意図したapply対象はSkill本文・references・evalsです。ただし、現行のtarget parserが認識するのは
空白を含まないunquotedな `diff --git a/... b/...` headerだけです。quotedまたは空白を含む追加sectionは
target検査から漏れてもpatch全体として `git apply` へ渡るため、toolのpreviewだけでは許可外pathが
ないことを保証できません。修正されるまでは、human reviewで全 `diff --git` sectionを確認してください。
validator失敗時はreverse patchによるrollbackを試みます。reverse checkまたはrollbackも失敗した場合は
変更が残り、手動確認が必要です。toolはcommitもpushもしません。詳しくは
[ルール昇格](docs/rule-promotion.md)を参照してください。

### 日本語構造sensorを評価する

日本語構造sensorはoptionalです。`scripts/analyze_ja.py analyze` を明示実行した場合だけ
GiNZAを読み込みます。dependency未導入やparse失敗の場合は、非致命のavailability resultを
返します。通常のreviewからinstall、model download、解析を自動実行しません。出力は
構造観測値であり、可読性やRR labelのground truthではありません。

`ab-report` は、各provider・case・repeatでLLM-onlyとLLM-plus-signalsを比較します。両providerが
入力に現れることは確認しますが、provider間で同じcase集合を使ったことは確認しません。改善として
数えるのは、RR recall、false positive、unnecessary revision、expected behavior accuracy、provider間の
risk disagreementに定義した方向の変化です。回帰、provider差拡大、この定義での改善なしを
`do-not-default` とし、改善が観測されても人間の確認なしに既定利用を有効化しません。install pin、
schema、CLI例は[日本語構文解析](docs/syntax-analysis.md)を参照してください。

関連文書:

- [コーパス運用](docs/corpus-workflow.md)
- [コーパスデータモデル](docs/corpus-data-model.md)
- [ルール昇格](docs/rule-promotion.md)
- [Agentによる調査](docs/agent-investigation.md)
- [日本語構文解析](docs/syntax-analysis.md)
- [ライセンスとプライバシー](docs/licensing-and-privacy.md)

## ポータビリティ

CodexとGitHub Copilotは、同じ `SKILL.md` に記載された共通の指示を使います。
`agents/openai.yaml` には、任意のCodex向けmetadataと暗黙起動を禁止する設定だけを記載します。
このファイルがなくても、ホストに依存しない共通の指示で動作します。

This is an independent, unofficial implementation. It does not reproduce the
ISO 24495-1 standard and does not claim ISO conformance or certification. See
[NOTICE.md](NOTICE.md) for sources and licenses.
