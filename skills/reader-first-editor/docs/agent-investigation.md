# Agentによる調査

状態: planned（未実装）

Agentはruleを積極的に考案する役ではなく、危険な一般化を壊す役として使う。toolは
provider-neutralなinvestigation bundleを生成し、CodexまたはCopilotが明示起動された場合だけ
そのbundleを読む。通常reviewへlocal corpusを暗黙に注入しない。

## 既定姿勢

```text
Default decision: DO NOT PROMOTE
```

有用なruleを見逃すcostより、有害なruleをcoreへ導入するcostを高く扱う。広いruleより狭い
rule、処方箋より観察、早い採用より `HOLD` を選ぶ。

## Investigationの順序

1. 既存ruleで説明できるか確認する。
2. 支持例のsource相関とconfounderを確認する。
3. clean・borderline・rejected sampleから反例を探す。
4. 最小反例を作り、仮説が広すぎる条件を特定する。
5. 発火例と非発火例のminimal pairで境界を調べる。
6. language、genre、reader、purpose、translation依存までscopeを縮める。
7. semantic、unnecessary revision、register、literal、repository-reviewの回帰を調べる。
8. 未説明の反例がなければproposal候補を作る。

## 役割

- **Pattern Miner**: 共通特徴をruleではなく仮説として記録し、confounderを示す。
- **Counterexample Hunter**: 反例と修正不要な類似例を最優先で探す。
- **Boundary Tester**: minimal pairから隠れた適用条件を特定する。
- **Regression Analyst**: false positive、semantic damage、genre bias、provider差を比較する。
- **Rule Reviewer**: 既存ruleで十分かを再確認し、既定をreject／hold側に置く。

同じAgentが複数役を担う場合も、output sectionと判断を分離する。proposal作成contextとは
別のfresh contextで反証reviewを行うことが望ましい。

## Bundle

bundleには、仮説、対象scope、record ID、source correlation、支持例、反例、known exception、
semantic invariants、既存rule、提案eval、未確認事項を含める。raw third-party textをrights確認
なしにbundleへ複製せず、reference-only recordは参照とhashだけを渡す。

Agentの出力はproposal recordのdraftであり、toolのstate transitionや人間の承認を代行しない。
未説明の反例があればdecisionを `HOLD` にし、情報が足りなければ
`NEEDS_MORE_EVIDENCE` にする。
