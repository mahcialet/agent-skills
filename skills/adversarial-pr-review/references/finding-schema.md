# Finding schema

findingは、変更によって導入・露呈し、実際の経路から到達できる問題を示す。第三者が同じ経路と
証拠を追って、成立するか確認・反証できる形にする。まだ確認できていない懸念、hypothesis、
残余リスクとは分ける。

## 必須項目

```text
ID / title
Priority: P0 | P1 | P2 | P3
Adversarial level: A0 | A1 | A2 | A3 | A4
Confidence: Confirmed | Strongly supported
Location
Contract / invariant reference
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

- **Location**: 問題があるchanged locationを、可能な限り狭く特定する。Location fieldには
  canonical locatorだけを1行で記録し、説明、API route、第2のlocatorを混ぜない。必要なら関連する
  差分外locationをCode pathやEvidenceに同じ形式で併記する。
  - Repository labelとlineを確認できた場合は、repository-root-relative pathと組み合わせ、
    `<repository>/<path>:<line>` または `<repository>/<path>:<start>-<end>` のvisible inline locatorで
    示す。Lineは1始まりとし、rangeは必要最小限にする。たとえば
    `sample-repo/src/policy.ts:16` とする。
  - Path separatorは `/` に正規化する。行番号だけのlabel、host固有のabsolute filesystem path、
    `file:` URL、home省略記号、drive、UNC、path中のcolon、空segment、`.`、`..`、Markdown linkは
    出力しない。Markdown linkはhostごとにrelative targetやline anchorの解釈が異なり、
    absolute pathをlink targetへ隠せるためである。
  - Repository labelを確認できない場合は `Repository label: unverified` とし、labelを創作せず、
    `src/policy.ts:16` のようにroot-relative pathだけを残す。
  - 正確なlineを確認できない場合も、lineを創作せずに省く。確認済みrepository labelは維持し、
    Locationには `sample-repo/src/policy.ts` のようなpathを記録する。
    `Location line status: unverified` で未確認状態を示し、確認済みsymbolがある場合だけ
    別fieldの `Confirmed symbol` も記録する。
- **Contract / invariant reference**: 破られたcriteriaまたはinvariantのsource pointerを示す。
  `Issue #123 / forbidden outcome bullet 1`、`Repository contract: schema unique constraint`、
  `Inferred invariant: one logical operation produces one side effect` のように由来を区別する。
  sourceに存在しないrequirement IDを作らない。
- **Actor / trigger**: 誰または何が、どのevent・input・failureでpathを起動するか。
- **Precondition**: 問題が成立するstate、権限、順序、競合、設定。
- **Code path**: entry pointから、守るべき条件が破られるstateと外から確認できる影響
  （observable effect）までの経路。
- **Broken invariant**: 常に保つべき条件と、どこで破られるか。
- **Impact**: 利用者、data、security、availability、cost、operationへの具体的影響。
- **Evidence**: diff、caller、schema、test、contract等の確認済み事実。
- **Reproduction or verification**: 安全な再現、static proof、または限定的な確認方法。
- **Fix direction**: 問題を防ぐために直すboundary/invariant。未検証の完全patchを断定しない。
- **False-positive condition**: どの未確認のconstraintやcontractが真なら、問題が成立しないか。

`Hypothesis` はfindingのconfidenceとして使わず、独立sectionへ置く。外部contract、runtime path、
production configなどを確認できず、問題が成立することを示せない場合に使う。
`Not applicable` は領域や検査項目の適用外を示す値であり、findingの確信度には使わない。

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

各主張について、source、調べた内容、結果、制約を記録する。diff以外を少なくとも1つ調べる
という件数だけの条件にはせず、その主張を支えるために必要な証拠を追う。

```text
E-01 | diff | changed idempotency check | check and write are separate
E-02 | schema | payments table | no unique constraint for request key
E-03 | caller | retry worker | same request can be submitted concurrently
E-04 | test | not executed | runner changed to send data externally
```

未実施検証は、実施済み・成功と混ぜない。

## Test evidence provenance

test evidenceは次の3分類を使い、互いに読み替えない。

- **claimed**: author、PR本文、ユーザーが成功を申告しただけ。
- **observed**: CI status、check result、保存済みlog等をreviewerが確認した。可能ならsourceと
  対象commit／head SHAを記録する。
- **executed**: reviewerが安全な環境で実行した。command、environment、result、制約を記録する。

unsafe、外部副作用、変更済みrunner等の理由で実行しなかったものは `Unexecuted validation` へ
分離する。testの存在や成功だけで、criterionを満たすと断定しない。

## Gate decisions

- **BLOCK**: 未解決のP0/P1、またはrepository policyがblockingと定義する確認済みfindingがある。
- **CONDITIONAL**: 重要なhypothesis、未確認contract、必要なfollow-up、またはmerge readinessに
  重要な未確認criteriaがある。
- **PASS**: 指定scope、取得できたcontract、確認したevidenceでblocking findingを確認しなかった。

これらはAIによるgate recommendationであり、approvalではない。`mode=gate` のreportには必ず
次を含める。

```text
Gate recommendation: BLOCK | CONDITIONAL | PASS
Approval status: NOT GRANTED
Human approval required: yes
Decision owner: <verified role or unresolved>
```

`Approval status` は常に `NOT GRANTED` とする。decision ownerを確認できなければ創作せず、
`unresolved` とする。`specification_status=partial` で重要なcriteriaが未確認の場合と、
業務要件適合を含むgateで `specification_status=missing` の場合は原則 `CONDITIONAL` とする。
明示された限定scopeに必要なcontractが十分なら、そのscopeでは `PASS` を出せる。確認済みP0/P1が
あれば `BLOCK` にできる。

recommendationはレポート内の判断に限る。`PASS` はmerge承認や安全保証ではなく、GitHub上の
stateも変更しない。
