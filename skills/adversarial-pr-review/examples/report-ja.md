# A2 review report: 並行retryによる二重反映

## Scope and parameters

- Target: `base...head` の決済retry変更
- Base / head: `main` / review対象branch
- Level / minimum / depth / mode: `A2` / `A1` / `standard` / `review`
- Selection rationale: 正規権限を持つclientが同じrequestを並行・再送でき、idempotencyと
  金額反映を扱うためA2
- Excluded scope: 外部決済事業者の本番挙動

## Findings

### F-001: 同じidempotency keyの並行requestが残高を二重反映する

- Priority: P1
- Adversarial level: A2
- Confidence: Strongly supported
- Location: `src/payments/service.ts` の存在確認後にledgerへinsertする変更箇所
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

## Unexecuted validation

本番providerへのrequestと課金を伴うintegration testは実行していない。代わりに、caller、transaction
境界、migration、refund実装をコード上で確認した。local concurrency testはfixtureが未整備のため未実施。

## Residual risks

- 外部providerが重複を除外する条件と、timeout時のresponseが何を示すかは未確認。
- A3以上のtenant改ざんやcredential compromiseは、このA2 reviewの上限外。

このreportが示すのは、指定scopeで確認した結果だけであり、安全性や無欠陥は保証しない。
