# ルール昇格

状態: implemented（investigation、regression gate、human approval、明示apply）

rule promotionはcorpus promotionと別のworkflowである。実例を評価可能なcorpusへ追加しても、
Skillの判断規則は変わらない。behavior-changing ruleの既定判断は `HOLD` または
`NEEDS_MORE_EVIDENCE` とする。structured investigation、human-unapproved proposal draft、
provider-neutralなregression集約、human approval artifact、rule patchの明示applyを実装している。

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

1件のcandidate、単一sourceの件数、頻度、固定閾値だけからruleを作らない。既存ruleで説明
できる場合はduplicateとして止め、観察のままで十分ならruleにしない。

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

反例が一つでも残る場合、多数決で無視しない。反例が成立しない条件までruleを狭められなければ
`HOLD`、証拠自体が不足する場合は `NEEDS_MORE_EVIDENCE` とする。

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

apply対象はhuman-reviewedなprose diffとeval updateである。初版ではcore referencesを
structured recordから自動生成せず、自動commit・pushもしない。

`rules propose --apply` は名前に `apply` を含むが、proposal artifactをlocal dataへ
保存するだけである。core ruleへの `rules apply` ではない。作成時のregressionは全て `not-run`、
human approvalはfalseで固定する。承認はproposal自体を書き換えず、別のimmutable artifactとして
保存する。

`rule-proposal.schema.json` へ適合することは、applyの許可ではない。schemaはproposalと
検証結果を受け渡す形式であり、regression結果、人間の承認、明示的な `--apply` は別の
runtime gateで再確認する。

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
reportを再計算し、改変されたreportを拒否する。pass reportだけを人間が承認でき、承認artifactは
proposal ID、report ID、exact diff hash、reviewer、理由を固定する。

`rules apply` が変更できるのは次だけである。

- `skills/reader-first-editor/SKILL.md`
- `skills/reader-first-editor/references/**/*.md`
- `skills/reader-first-editor/evals/*.yaml`

rule targetとeval targetの両方を必要とする。binary、削除、rename、path traversal、symlink、no-op、
proposalにないeval ID、対象fileの未commit変更を拒否する。`git apply --check` 後にpatchを適用し、
content validatorとSkill validatorが失敗した場合はpatchをrollbackする。commitとpushは行わない。

## Decision

判定は `PROMOTE`、`REJECT`、`HOLD`、`NEEDS_MORE_EVIDENCE` を使う。`PROMOTE` はproposalが
review可能という意味であり、即時applyや安全保証ではない。
