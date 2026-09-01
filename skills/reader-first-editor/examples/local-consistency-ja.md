# DB定義の局所整合性review例

## 対象

DB定義表からaudit timestampとして同じ役割を持つ24列を確認したところ、次の分布だったとする。

```text
timestamptz: 22
timestamp:    2
```

少数例は `foo.published_at` と `bar.completed_at` である。

## candidate生成

まず、全DB列の最多型ではなく、audit timestampというsemantic peer groupの根拠と全memberを
確認する。Markdown tableを構造化できる場合はtype、nullable、default、constraint、comment、
source locationを抽出する。dominance ratioはcandidate生成のtripwireであり、誤り判定ではない。

## 根拠が見つからない場合

```text
[局所整合性][UNEXPLAINED]

audit timestamp 24列のうち、22列が `timestamptz`、2列が `timestamp` です。

対象:
- foo.published_at
- bar.completed_at

DDL、migration、column comment、testを確認しましたが、この2列だけtimezoneなし型を使う理由は
確認できませんでした。

少数派であることだけでは誤りと判断できません。意図的な例外か、定義の反映漏れかを確認して
ください。reviewでは型を変更しません。
```

この場合の `anomaly_status` は `UNEXPLAINED` である。repository evidenceのclaimは、探索範囲内に
理由がなければ `evidence_status: UNSUPPORTED` と分けて記録する。

## 意図的な例外の場合

ADRとcolumn commentに「外部端末が送った現地時刻をtimezoneなしで保存する」と記載されていれば、
そのcolumnは `EXPLAINED` とする。確認済みcandidateとしてcoverageへ残すが、型の変更を提案しない。

## 明示規則と矛盾する場合

schema policyとtestがaudit timestampを `timestamptz` に限定し、例外規定もない場合は、具体的な
反証を示して `anomaly_status: CONTRADICTED`、`evidence_status: CONTRADICTED` とする。少数派で
あることではなく、明示規則との矛盾が判定根拠である。

## 比較しない境界例

`created_at timestamptz`、`birth_date date`、`local_time timestamp` を、近くに記載されていることや
全体頻度だけで同じgroupにしない。監査日時、暦日、利用者の現地時刻は役割が異なる可能性がある。
