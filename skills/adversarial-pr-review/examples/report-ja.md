# A2 review report: 並行retryによる二重反映

## Scope and parameters

- Target: `base...head` の決済retry変更
- Repository label: `payments-api`
- Base / head: `main` / review対象branch
- Level / minimum / depth / mode: `A2` / `A1` / `standard` / `review`
- Selection rationale: 正規権限を持つclientが同じrequestを並行・再送でき、idempotencyと
  金額反映を扱うためA2
- Excluded scope: 外部決済事業者の本番挙動
- Identifier scope: new report

## Review contract

- Specification status: partial
- Purpose / actors: 正規clientによるtimeout後のretryを、二重反映せず処理する
- Criteria sources:
  - PR-declared criterion: PR description / retryは同じidempotency keyで安全に再送できる
  - Repository contract: ledger schema、migration、既存refund実装
  - Inferred invariant: 1つの論理requestは高々1回だけ残高へ反映される
- Expected outcomes: 同じkeyのretryは既存結果を返し、ledgerとbalanceを1回だけ更新する
- Forbidden outcomes: 同じ論理requestによる複数ledger entryまたは残高の二重反映
- Declared scope / non-scope: payment APIとledger変更 / 外部providerの本番内部実装
- Declared impact: payment API、ledger、balance
- Unresolved decisions: 外部providerが同じkeyをdeduplicateする正確な条件
- Stop / recovery / handoff: 二重反映を検出した場合のreconciliation手順とhandoff ownerは未確認
- Final decision owner: unresolved

## Requirement traceability

| Source reference | Kind | Requirement / forbidden outcome | Implementation path | Test / evidence | Status |
|---|---|---|---|---|---|
| PR description / retry criterion | PR-declared criterion | 同じkeyのretryで二重反映しない | API → retry wrapper → `createPayment` → ledger / balance | PRのtest成功申告はclaimed。static pathはE-01〜E-04 | Violated |
| Ledger and refund implementation | inferred invariant | 1つの論理requestは高々1回だけcommitされる | existence check → insert → balance update | unique constraintなし。refund pathはatomic insert | Violated |
| Payment provider contract | reviewer hypothesis | provider側でも同じkeyをdeduplicateする | external API | versionと認証情報を確認できない | Unverified |

## Impact comparison

- Declared impact: payment API、ledger、balance
- Discovered impact: timeout時に同じkeyを再送するretry worker
- Undeclared impact requiring follow-up: reconciliation batchが重複entryをどう扱うか

## Coverage gap audit

- Inspection separation: same reviewerのfresh pass。独立reviewerは利用していないため、独立性に制約がある。
- Initial findings were not used as the completion criterion: 初回候補を固定し、idempotency keyの変更obligationから再探索した。

### Change-obligation coverage

| Changed concept | Route inspected | Status | Evidence | Linked finding / hypothesis |
|---|---|---|---|---|
| idempotency keyのat-most-once契約 | API producer → service check → ledger write → balance side effect → migration／refund test | Inspected | E-01〜E-04 | F-001 |
| reconciliation batchへの伝播 | batch consumerと重複entryの扱い | Unverified | production batch設定を取得できない | Residual risk |

### Relational-invariant coverage

| Field / state group | Relationship checked | Status | Evidence |
|---|---|---|---|
| idempotency key、ledger entry、balance update | 1 logical requestに対するcardinality、checkとcommitのatomicity、duplicate時のstate | Inspected | E-01〜E-04 |

### Repository-rule obligations

| Base instruction | Triggering change | Required companion | Status | Evidence |
|---|---|---|---|---|
| base側instructionは未取得 | transaction behaviorの変更 | companion requirementを確定できない | Unverified | base instructionを取得できない制約 |

### Blind-spot result

fresh passではF-001と同じbroken invariantへ収束した。追加findingは作らず、未確認のbatch設定を
Residual risksへ分離した。`Inspected`をcorrectness保証とは扱わない。

## Findings

### F-001: 同じidempotency keyの並行requestが残高を二重反映する

- Priority: P1
- Adversarial level: A2
- Confidence: Strongly supported
- Location: `payments-api/src/payments/service.ts:87`
- Contract / invariant reference: PR description / retry criterion、および
  `Inferred invariant: one logical request produces at most one committed balance update`
- Actor / trigger: 正規に認証されたclientが、同じidempotency keyで2requestを並行送信する
- Precondition: 両transactionが相手の未commit rowを確認できず、同じaccountを更新できる
- Code path: API handler → retry wrapper → `createPayment` → 存在確認 → ledger insert → balance update
- Broken invariant: 1つの論理requestは高々1回だけ残高へ反映される
- Impact: 残高とledger entryが二重に増え、手動reconciliationが必要になる
- Evidence: callerはtimeout後に同じkeyでretryし、存在確認とinsertは別statementで、schemaに
  idempotency keyのunique constraintがない
- Reproduction or verification: 2transactionをbarrierで存在確認後に停止し、同時にcommitする
  local DB testを追加すれば確認できる
- Fix direction: check-then-writeではなく、DBが強制するunique constraintとatomic insert/upsertで
  winnerを決め、残高更新を同じtransactionへ入れる
- False-positive condition: production schemaに未確認のunique indexまたは同等のserializable
  constraintがあり、残高更新まで原子的に重複を拒否する場合

## Hypotheses

- 外部決済APIも同じkeyを原子的にdeduplicateする可能性はあるが、確認できていない。また、その挙動
  だけではlocal ledgerとbalanceのatomicityを証明できないため、F-001の根拠には含めていない。

## Evidence ledger

| ID | Source | Checked | Result / limitation |
|---|---|---|---|
| E-01 | diff + changed file | idempotency checkとwrite | 別statementで実行される |
| E-02 | caller | timeout時のretry | 同じkeyで再送可能 |
| E-03 | schema / migrations | ledger constraint | idempotency keyのunique constraintなし |
| E-04 | symmetric implementation | refund path | atomic insertで重複を拒否している |
| E-05 | external contract | payment provider | 認証情報がなく未確認 |

## Test evidence

| Test / check | Provenance | Source / command | Result | Limitation |
|---|---|---|---|---|
| payment policy tests | claimed | PR description | 18 passedと申告 | CI result、head SHA、logをreviewerは確認していない |

## Unexecuted validation

本番providerへのrequestと課金を伴うintegration testは実行していない。代わりに、caller、transaction
境界、migration、refund実装をコード上で確認した。local concurrency testはfixtureが未整備のため未実施。

## Residual risks

- 外部providerが重複を除外する条件と、timeout時のresponseが何を示すかは未確認。
- A3以上のtenant改ざんやcredential compromiseは、このA2 reviewの上限外。

このreportが示すのは、指定scopeで確認した結果だけであり、安全性や無欠陥は保証しない。
