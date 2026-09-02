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
- positive、negative、boundary eval候補。case IDをcategory間で再利用しない
- 未説明の反例数とdecision理由

反例が一つでも残る場合は、多数決で無視しない。反例が成立しない範囲までruleを狭められなければ
`HOLD` とする。証拠自体が不足する場合は `NEEDS_MORE_EVIDENCE` とする。

## Apply gate

`rules apply` の既定動作はpreviewであり、`--apply` と承認artifactがそろうまでfileを変更しない。
toolが確認するのは、pass report、exact diff、空でないreviewer・理由を持つcaller-supplied artifactである。
reviewerが人間かは認証しないため、人間による明示reviewはtool外の運用責任である。
少なくとも次の場合はapplyを拒否する。

- provenance reviewが完了していない
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

`regression-plan` はbundled eval全件、callerが `--corpus-record` で選んだpromoted record、proposalの
positive／negative／boundary evalを含む。promoted record全件は自動選択しない。provider、model、
model version、host version、repeat回数を固定し、CodexとGitHub Copilotを必須providerとして記録する。
local corpusのraw textはplanへ複製せず、record path、content hash、取得要否だけを保持する。

`regression-ingest` はplanと同じcase順、provider metadata、repeat indexを検証してlocal保存する。
各caseは `pass`、`fail`、`unsupported`、`error` を区別し、semantic preservation、unnecessary
revision、literal、register、expected behaviorの一致を記録する。`unsupported` は通常のfailureと
件数を分けるが、gateは通さない。

`regression-report` は全provider・repeatの不足と重複を検出し、existing、corpus、positive、
negative、boundary、no-change accuracyを集約する。`approve` と `apply` は保存済みplanとrunから
reportを再計算し、改変されたreportを拒否する。approval artifactを作成できるのはpass reportだけで
ある。承認artifactにはproposal ID、report ID、exact diff hash、caller-suppliedなreviewer、理由を
固定する。

`rules apply` が変更できるのは次だけである。

- `skills/reader-first-editor/SKILL.md`
- `skills/reader-first-editor/references/**/*.md`
- `skills/reader-first-editor/evals/*.yaml`

rule targetとeval targetの両方が必要である。binary、削除、rename、path traversal、symlink、no-op、
対象fileの未commit変更は拒否する。eval targetの追加行からcase IDを抽出し、proposalのpositive、
negative、boundary ID集合と双方向で一致しないpatchも拒否する。`git apply --check` 後にpatchを適用し、
content validatorとSkill validatorが失敗した場合はpatchをrollbackする。commitとpushは行わない。

## Decision

判定には `PROMOTE`、`REJECT`、`HOLD`、`NEEDS_MORE_EVIDENCE` を使う。`PROMOTE` が示すのは、
proposalを人間がreviewできる状態になったことだけである。即時applyや安全保証を意味しない。
