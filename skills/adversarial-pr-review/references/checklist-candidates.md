# Checklist candidate conversion

ユーザーがfindingを再利用可能なreview checklistへ変換するよう明示した場合だけ使う。
review中にchecklistやrepository fileを自動変更しない。

## Classification

- `new`: 既存checklistに同じtrigger、invariant、verificationがない。
- `update`: 既存entryは近いが、境界・成立条件・検証方法を補う必要がある。
- `duplicate`: 既存entryが同じfailure mechanismと検証を十分に覆う。
- `reject`: 一般化できない、変更固有、証拠不足、style preference、または安全なcheckとして
  実行できない。

語が似ているだけでduplicateにせず、actor/trigger、broken invariant、evidence routeを比較する。

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

findingのpriorityをchecklistの恒久severityとして固定しない。同じmechanismでもassetやimpactに
よりpriorityが変わるため、candidateには想定levelと適用条件を中心に残す。

既存checklistとの比較結果、更新対象entry、失われ得るscopeを示す。ユーザーが別途編集を依頼
するまではcandidate reportだけを返す。
