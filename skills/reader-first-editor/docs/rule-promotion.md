# ルール昇格

状態: implemented（investigation、regression gate、human approval、明示apply）

rule promotionはcorpus promotionとは別のworkflowである。実例を評価に使えるcorpusへ追加しても、
それだけではSkillの判断規則は変わらない。behavior-changing ruleの既定判断は `HOLD` または
`NEEDS_MORE_EVIDENCE` とする。structured investigation、human-unapproved proposal draft、
provider-neutralなregression集約、human approval artifact、rule patchの明示applyは実装済みである。

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
human approval
  ↓
明示的なapply
```

1件のcandidate、単一sourceの件数、頻度、固定閾値だけを根拠にruleを作らない。既存ruleで
説明できる場合はduplicateとして止め、観察のままで十分ならruleにしない。

## Proposal gate

proposalには次が必要である。

- 複数の独立した支持例とsource diversity
- clean sampleを含む意図的なcounterexample search
- 発火すべき例と発火すべきでない例のboundary pair
- language、genre、reader、purpose、native・translationのscope
- 頻度以外のmechanismとsemantic risk
- 既存ruleとの重複確認
- positive、negative、boundary eval候補
- 未説明の反例数とdecision理由

反例が一つでも残る場合は、多数決で無視しない。反例が成立しない条件までruleを狭められなければ
`HOLD` とする。証拠自体が不足する場合は `NEEDS_MORE_EVIDENCE` とする。

## Apply gate

`rules apply` の既定動作はpreviewであり、`--apply` と人間の承認がそろうまでfileを変更しない。
少なくとも次の場合はapplyを拒否する。

- provenance reviewが完了していない
- counterexample fixtureまたはboundary fixtureがない
- 未説明のcounterexampleが残る
- languageまたはgenre scopeがない
- rule diffがない、no-op、既存ruleのduplicate
- 頻度やhard thresholdだけを根拠にしている
- human approvalがない
- existing eval、semantic preservation、unnecessary revision、literal、registerにregressionがある
- positive、negative、boundary evalのいずれかがない
- candidateまたはcorpus promotionからruleへ直接遷移している

applyの対象はhuman-reviewedなprose diffとeval updateである。初版ではcore referencesを
structured recordから自動生成しない。commitとpushも自動では行わない。

`rules propose --apply` は名前に `apply` を含むが、proposal artifactをlocal dataへ保存するだけで
ある。core ruleへ適用する `rules apply` とは異なる。作成時のregressionは全て `not-run`、
human approvalはfalseで固定する。承認はproposal自体を書き換えず、別のimmutable artifactとして
保存する。

`rule-proposal.schema.json` へ適合しても、それだけではapplyできない。schemaはproposalと検証結果を
受け渡す形式である。regression結果、人間の承認、明示的な `--apply` は、別のruntime gateで
再確認する。

## Regression workflow

portableなPython toolはCodexやGitHub Copilotを直接起動しない。実行計画と結果形式を固定し、
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

`regression-plan` はbundled eval全件、promoted local corpus、proposalのpositive／negative／
boundary evalを含む。provider、model、model version、host version、repeat回数を固定し、Codexと
GitHub Copilotを必須providerとして記録する。local corpusのraw textはplanへ複製せず、record path、
content hash、取得要否だけを保持する。

`regression-ingest` はplanと同じcase順、provider metadata、repeat indexを検証してlocal保存する。
各caseは `pass`、`fail`、`unsupported`、`error` を区別し、semantic preservation、unnecessary
revision、literal、register、expected behaviorの一致を記録する。`unsupported` は通常のfailureと
件数を分けるが、gateは通さない。

`regression-report` は全provider・repeatの不足と重複を検出し、existing、corpus、positive、
negative、boundary、no-change accuracyを集約する。`approve` と `apply` は保存済みplanとrunから
reportを再計算し、改変されたreportを拒否する。人間が承認できるのはpass reportだけである。
承認artifactにはproposal ID、report ID、exact diff hash、reviewer、理由を固定する。

`rules apply` が変更できるのは次だけである。

- `skills/reader-first-editor/SKILL.md`
- `skills/reader-first-editor/references/**/*.md`
- `skills/reader-first-editor/evals/*.yaml`

rule targetとeval targetの両方が必要である。binary、削除、rename、path traversal、symlink、no-op、
proposalにないeval ID、対象fileの未commit変更は拒否する。`git apply --check` 後にpatchを適用し、
content validatorとSkill validatorが失敗した場合はpatchをrollbackする。commitとpushは行わない。

## Decision

判定には `PROMOTE`、`REJECT`、`HOLD`、`NEEDS_MORE_EVIDENCE` を使う。`PROMOTE` が示すのは、
proposalを人間がreviewできる状態になったことだけである。即時applyや安全保証を意味しない。
