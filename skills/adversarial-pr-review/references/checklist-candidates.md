# Checklist candidate conversion

ユーザーがfindingを再利用できるreview checklistへ変換するよう明示した場合だけ使う。
変換結果は候補として返し、review中にchecklistやrepository fileを自動変更しない。

## Classification

- `new`: 既存checklistに同じtrigger、invariant、verificationがない。
- `update`: 既存entryは近いが、問題が起きる境界・成立条件・検証方法を補う必要がある。
- `duplicate`: 既存entryが、同じ問題が起きる仕組みと検証方法を十分に覆う。
- `reject`: 一般化できない、変更固有、証拠不足、style preference、または安全なcheckとして
  実行できない。

語が似ているだけでduplicateにしない。actor/trigger（誰または何が、どのevent・input・failureで
pathを起動するか）、守れなくなる条件を示すbroken invariant、確認に使うevidence routeを比較する。

## Candidate fields

`assets/checklist-entry.example.yml` を出力形の参考にする。

```text
source_finding
classification
title
trigger
invariant
evidence_to_collect
verification
applies_when
does_not_apply_when
suggested_level
notes
```

findingのpriorityをchecklistの恒久severityとして固定しない。同じ問題が起きる仕組みでも、対象や
影響によってpriorityが変わるため、candidateには想定levelと適用条件を中心に残す。

既存checklistとの比較結果、更新対象entry、失われ得る適用範囲（scope）を示す。ユーザーが
別途編集を依頼するまでは、candidate reportだけを返す。
