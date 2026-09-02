# ルール昇格

状態: implemented（investigation、regression gate、caller-supplied approval、明示的なapply）

rule promotionはcorpus promotionとは別のworkflowである。実例を評価に使えるcorpusへ追加しても、
それだけではSkillの判断規則は変わらない。behavior-changing ruleの既定判断は `HOLD` または
`NEEDS_MORE_EVIDENCE` とする。structured investigation、human-unapproved proposal draft、
provider-neutralなregression集約、caller-supplied approval artifact、rule patchの明示的なapplyは
実装済みである。人間によるreviewはtool外の運用要件である。

## Workflow

```text
accepted / rejected corpus
  ↓
rule investigation
  ↓
structured proposal
  ↓
counterexample / boundary / regression review
  ↓
rule diff
  ↓
tool外のhuman review / approval artifact
  ↓
明示的なapply
```

1件のcandidate、単一sourceから得た件数、頻度、固定閾値だけを根拠にruleを作らない。既存ruleで
説明できる場合はduplicateとして止め、観察のままで十分ならruleにしない。

## Proposal gate

proposalには次が必要である。

- 複数の独立した支持例とsource diversity
- clean sampleを含む意図的なcounterexample search
- 発火すべき例と発火すべきでない例のboundary pair
- language、genre、reader、purpose、native・translationのscope
- 頻度以外のmechanismとsemantic risk
- 既存ruleとの重複確認
- positive、negative、boundary eval候補。最終的にcase IDをcategory間で再利用しない
- 未説明の反例数とdecision理由

反例が一つでも残る場合は、多数決で無視しない。反例が成立しない範囲までruleを狭められなければ
`HOLD` とする。証拠自体が不足する場合は `NEEDS_MORE_EVIDENCE` とする。

現行のinvestigation validatorはboundary pairの各fieldが空でないことと、選択済みcontrolの記載漏れを
確認するが、`fires` がsupport recordか、両record IDが実在するか、意味上のminimal pairかは確認しない。
また、`rules propose` はcategory間でeval IDが重複したproposalも保存できる。これらはproposal作成時の
runtime gateではなく、人間reviewと後段のproposal validationで確認する。`regression-plan` と
`rules apply` はeval IDのcategory間重複を拒否する。

## Apply gate

`rules apply` の既定動作はpreviewであり、`--apply` と承認artifactがそろうまでfileを変更しない。
toolが確認するのは、pass report、exact diff、空でないreviewer・理由を持つcaller-supplied artifactである。
reviewerが人間かは認証しないため、人間による明示reviewはtool外の運用責任である。
少なくとも次の場合はapplyを拒否する。

- proposalのcaller-suppliedな `provenance_reviewed` flagがtrueではない
- counterexample fixtureまたはboundary fixtureがない
- 未説明のcounterexampleが残る
- languageまたはgenre scopeがない
- rule diffがない、またはno-opである
- Agent resultが `duplicate_rule`、`frequency_only`、`fixed_threshold_only` を申告している
- approval artifactがない
- existing eval、semantic preservation、unnecessary revision、literal、registerにregressionがある
- positive、negative、boundary evalのいずれかがない
- candidateまたはcorpus promotionからruleへ直接遷移している

運用上、applyの対象は人間がreviewしたprose diffとeval updateに限定する。初版ではcore referencesを
structured recordから自動生成しない。commitとpushも自動では行わない。
toolはrule diffの自然言語からduplicate、頻度依存、hard threshold依存を推論しない。Agentの
structured flagとdiffの整合、既存ruleとの照合はtool外の人間reviewで確認する。
counterexample gateもstructuredな `unexplained` と、選択済みcontrolの `explained`／boundaryへの
記載を確認する。説明内容が妥当かはtool外の人間reviewで確認する。

`rules propose --apply` は名前に `apply` を含むが、proposal artifactをlocal dataへ保存するだけで
ある。core ruleへ適用する `rules apply` とは異なる。作成時のregressionは全て `not-run`、
human approvalはfalseで固定する。承認情報はproposal自体を書き換えず、別のimmutable artifactとして
保存する。ここでimmutableはtoolが同じlocal pathを上書きしないことを指し、全fieldをartifact IDへ
含めることや、外部編集を暗号学的に検出することまでは意味しない。

`rule-proposal.schema.json` へ適合しても、それだけではapplyできない。schemaはproposalと検証結果を
受け渡すための形式である。regression結果、approval artifact、明示的な `--apply` は別のruntime gateで
再確認する。

## Regression workflow

portableなPython toolはCodexやGitHub Copilotを直接起動しない。実行計画と結果形式を固定して、
各hostで実行した結果を取り込み、同じ基準で集約する。

```text
rules regression-plan
  ↓
各providerでplanの全caseを指定repeat回数だけ実行
  ↓
rules regression-ingest
  ↓
rules regression-report
  ↓
rules approve
  ↓
rules apply（既定preview、--applyで変更）
```

`regression-plan` は、既定の `--eval-dir` にあるbundled eval全件、callerが `--corpus-record` で
選んだpromoted record、proposalのpositive／negative／boundary evalを含む。`--eval-dir` を明示すると
そのdirectoryへ置き換わり、Skillのbundled eval directoryか、全suiteを含むかは検証しない。
bundled evalに `expected_risks`、`expected_statuses`、`expected_evidence_types` がある場合は、
外部runnerが構造化された期待値を照合できるようplanへ保持する。これらのfieldを指定する場合は
1件以上の値が必要であり、期待値がないfieldは省略する。`expected_statuses`と
`expected_evidence_types`はmodeにかかわらず対で指定する。1件のeval caseは1件のclaimを表し、
`expected_statuses`は1件だけを指定する。`VERIFIED`／`CONTRADICTED`ではリポジトリ内の
照合関係だけ、`SUPPORTED-BY-CITATION`では`CITATION`だけ、`UNSUPPORTED`では
`EVIDENCE-GAP`だけ、`UNVERIFIED`では`UNVERIFIED`だけをevidence typeとして許可する。
bundled evalが `expected_behavior` を明示した場合もその値を保持する。省略時だけ、`review`／
`repository-review` を `review-only`、その他のmodeを `context-dependent` として補う。
promoted record全件は自動選択しない。provider、model、
model version、host version、repeat回数を固定し、CodexとGitHub Copilotを必須providerとして記録する。
local corpusのraw textはplanへ複製せず、record path、content hash、取得要否だけを保持する。
manual recordのcontent hashはrecordに保存されたcaller-supplied値であり、plan作成時にも再計算しない。
structured oracleを追加したplan／runのschema versionは2である。version 1のplan／runは
structured oracle／observationを持たないlegacy artifactとして、同じversionの組合せに限り読取りを
継続する。legacy artifactからreportを再表示できるが、approvalとrule applyには使用できない。
rule promotionを続ける場合はversion 2のplanを再生成し、regressionを再実行する。version 1と2を
混在させたrunの取込みも拒否する。

`regression-ingest` はplanと同じcase順、provider metadata、repeat indexを検証してlocal保存する。
planに構造化された期待値がある `pass` caseでは、外部runnerの `observed_risks`、
`observed_statuses`、`observed_evidence_types` が期待値と完全一致することも検証する。`fail` caseは
期待値と異なる実測値を保存でき、`unsupported`／`error` caseは取得できなかった観測fieldを
省略できる。
各caseは `pass`、`fail`、`unsupported`、`error` を区別し、semantic preservation、unnecessary
revision、literal、register、expected behaviorの一致を記録する。`unsupported` は通常のfailureと
件数を分けるが、gateは通さない。

`regression-report` は全provider・repeatの不足と重複を検出し、existing、corpus、positive、
negative、boundary、no-change accuracyを集約する。`approve` と `apply` は保存済みplanとrunから
reportを再計算し、改変されたreportを拒否する。approval artifactを作成できるのはpass reportだけで
ある。承認artifactにはproposal ID、report ID、exact diff hash、caller-suppliedなreviewer、理由を
固定する。

`rules apply` が意図して許可するtargetは次だけである。

- `skills/reader-first-editor/SKILL.md`
- `skills/reader-first-editor/references/**/*.md`
- `skills/reader-first-editor/evals/*.yaml`

rule targetとeval targetの両方が必要である。現行parserは、空白を含まないunquotedな
`diff --git a/... b/...` headerだけをtarget sectionとして認識する。そのため、quotedまたは空白を含む
追加sectionはtarget一覧と許可path検査から漏れる一方、patch全体は後段の `git apply` に渡る。
修正されるまでは、previewの `targets` だけで許可外pathがないとは判断せず、人間が全
`diff --git` sectionを確認する。

認識したsectionについては、binary、削除、rename、path traversal、symlink、no-op、対象fileの
未commit変更を拒否する。previewはpatchを一時領域へ適用し、適用後のeval suiteに新規追加された
`cases` を解析する。proposalのpositive、negative、boundary ID集合との双方向一致に加え、
regression planへ固定したinput、期待結果、保持事項、禁止claimなどのfixture内容との一致も確認する。
metadataなど `cases` 外に同じIDがあるだけのpatchは拒否する。`git apply --check` 後にpatchを適用し、
content validatorとSkill validatorが失敗した場合はreverse patchによるrollbackを試みる。reverse check
またはrollbackにも失敗した場合は変更がworktreeへ残り、errorは手動確認を求める。commitとpushは
行わない。

## Decision

判定には `PROMOTE`、`REJECT`、`HOLD`、`NEEDS_MORE_EVIDENCE` を使う。`PROMOTE` が示すのは、
proposalを人間がreviewできる状態になったことだけである。即時applyや安全保証を意味しない。
