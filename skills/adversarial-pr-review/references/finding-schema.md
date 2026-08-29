# Finding schema

findingは、変更によって導入・露呈する到達可能な問題を、第三者が反証できる形で示す。
懸念、hypothesis、残余リスクと分離する。

## 必須項目

```text
ID / title
Priority: P0 | P1 | P2 | P3
Adversarial level: A0 | A1 | A2 | A3 | A4
Confidence: Confirmed | Strongly supported
Location
Actor / trigger
Precondition
Code path
Broken invariant
Impact
Evidence
Reproduction or verification
Fix direction
False-positive condition
```

- **Location**: 最も狭いchanged location。必要なら関連する差分外locationも併記する。
- **Actor / trigger**: 誰または何が、どのevent・input・failureでpathを起動するか。
- **Precondition**: 問題が成立するstate、権限、順序、競合、設定。
- **Code path**: entry pointからbroken state・observable effectまでの経路。
- **Broken invariant**: 常に保つべき条件と、どこで破られるか。
- **Impact**: 利用者、data、security、availability、cost、operationへの具体的影響。
- **Evidence**: diff、caller、schema、test、contract等の確認済み事実。
- **Reproduction or verification**: 安全な再現、static proof、または限定的な確認方法。
- **Fix direction**: 解決すべきboundary/invariant。未検証の完全patchを断定しない。
- **False-positive condition**: どの隠れたconstraintやcontractが真なら問題が成立しないか。

`Hypothesis` はfindingのconfidenceとして使わず、独立sectionへ置く。外部contract、runtime path、
production configなどを確認できず、成立を証明できない場合に使う。`Not applicable` は領域や
検査項目の適用外を示す値であり、findingの確信度には使わない。

## Priority

- **P0**: 即時の重大障害、広範な不可逆損失、または現実的なcritical compromise。mergeを
  止め、緊急対応が必要。
- **P1**: 重大なcorrectness/security/data loss/availability問題。通常はmerge前に修正する。
- **P2**: 限定条件での実害、回復可能な障害、重要な運用・互換性問題。修正または明示的受容が必要。
- **P3**: 低影響だが具体的で到達可能な問題。style preferenceや一般的改善案は含めない。

PriorityをA-levelから導かない。たとえばA1のdata lossはP1になり得て、A3の防御強化案でも
到達性が低ければfindingではなくhypothesisになり得る。

## Confidence

- **Confirmed**: 安全な再現、決定的なstatic path、test、constraint等で成立を確認した。
- **Strongly supported**: 複数の一次証拠でpathとinvariant breakを支えるが、環境依存の再現は
  行っていない。
- **Hypothesis**: 証拠またはcontractが不足。findingから分離する。
- **Not applicable**: 検査領域が対象外。findingには使用しない。

## Evidence ledger

claimごとにsource、調べた内容、結果、制約を記録する。diff以外を少なくとも1つ調べたことを
形式的に要求するのではなく、主張を支えるために必要な証拠を追う。

```text
E-01 | diff | changed idempotency check | check and write are separate
E-02 | schema | payments table | no unique constraint for request key
E-03 | caller | retry worker | same request can be submitted concurrently
E-04 | test | not executed | runner changed to send data externally
```

未実施検証は、実施済み・成功と混ぜない。

## Gate decisions

- **BLOCK**: 未解決のP0/P1、またはrepository policyがblockingと定義する確認済みfindingがある。
- **CONDITIONAL**: 限定条件付きの受容、重要なhypothesis、未確認contract、必要なfollow-upがある。
- **PASS**: 指定scopeと証拠でblocking findingを確認しなかった。

decisionはレポート内の判断に限る。`PASS` は安全保証ではなく、GitHub上のstateも変更しない。
