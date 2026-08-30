# ルール調査の実行契約

このreferenceは、利用者がlocal corpusからのrule investigationを明示した場合だけ読む。
通常の `review`、`revise-safe`、`repository-review` ではlocal bundleを探索・読込みしない。

## 入力

`rules bundle --apply` が生成した `bundle.json` を使う。bundle内のrecordはmetadataとlocal
`record_path`への参照であり、raw textのcopyではない。rightsとprivacyを保ち、明示選択された
record以外へ調査scopeを広げない。`reference-only` recordの本文を推測しない。

## 既定判断

```text
Default decision: HOLD
```

支持例の件数を採用理由にせず、次の順で反証する。

1. Counterexample Hunterとして、clean・borderline・rejected recordから反例を探す。
2. Pattern Minerとして、source correlation、confounder、既存ruleで説明可能かを確認する。
3. Boundary Testerとして、発火例と非発火例のminimal pairを作る。
4. Regression Analystとして、semantic、unnecessary revision、literal、registerのriskと
   positive／negative／boundary eval候補を分ける。
5. Rule Reviewerとして、scopeをさらに狭められないか再確認する。

役割ごとの観察と結論を混ぜない。分からない点を肯定へ補完しない。固定閾値だけ、頻度だけ、
一つのcorrelation groupだけ、既存ruleのduplicate、provenance未確認は `PROMOTE` にしない。

## 出力

`schemas/investigation.schema.json` に適合するJSONを作る。未説明のcounterexampleが一つでも
残る場合は `HOLD`、支持・control・scopeが不足する場合は `NEEDS_MORE_EVIDENCE` にする。
`PROMOTE` はrule proposalを人間がreviewできるという意味に限り、coreへのapplyではない。

`PROMOTE` には少なくとも次が必要である。

- provenance review済み
- 独立したsupport correlation groupが2件以上
- counterexample search済み、unexplained 0件
- cleanまたはborderline control
- boundary pair
- 頻度以外のmechanism
- existing rule analysisとsemantic risk
- positive、negative、boundary eval候補

toolのgateが `PROMOTE` を `HOLD` へ止めた場合、blockerを削除したように見せるためresultを
書き換えない。仮説を狭めて再調査するか、`HOLD`／`NEEDS_MORE_EVIDENCE` として保存する。
