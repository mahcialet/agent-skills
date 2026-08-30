# ルール昇格

状態: planned（未実装）

rule promotionはcorpus promotionと別のworkflowである。実例を評価可能なcorpusへ追加しても、
Skillの判断規則は変わらない。behavior-changing ruleの既定判断は `HOLD` または
`NEEDS_MORE_EVIDENCE` とする。

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

## Decision

判定は `PROMOTE`、`REJECT`、`HOLD`、`NEEDS_MORE_EVIDENCE` を使う。`PROMOTE` はproposalが
review可能という意味であり、即時applyや安全保証ではない。
