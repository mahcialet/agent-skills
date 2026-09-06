# State and recovery

## 保存構造

状態は配布Skillやtrusted configと分離し、privateなworkspaceに保存する。

```text
<work-dir>/<workspace-id>/
├── workspace.json                  # workspace IDとnon-secret profile binding
├── state.sqlite3
├── proposals/<proposal-id>/proposal.md
│   └── revisions/0001/{base.json,intent.json,metadata.json,...}
├── receipts/<operation-id>.json
├── locks/<target-hash>.lock
└── templates/{candidates,approved}/
```

revisionとreceiptはimmutableで、再検証により内容が変わると新revisionを追加する。proposal/state/historyは
SQLiteが正本で、proposal.mdは初回の人間向けsummaryである。履歴は削除せずREJECTED/SUPERSEDEDで
処理済みにできる。

人間のcontent approvalを記録する場合はproposal ID、revision、全artifactのcontent hash、approver、
理由へbindingする。別revisionへ自動継承せず、write permissionの代わりにも使わない。

## State

- DRAFT / PREPARED: artifact保存済みの準備段階。DRAFTで中断した場合は`revalidate`で再開する。
- READY: apply前の全local gateを通過。
- PENDING_PERMISSION: 必要permission不足。remote mutation 0。
- NEEDS_REMERGE: remote baseが変化。古いproposalのapprovalは再利用しない。
- NEEDS_REVIEW: markup、protected section、visibility、strict concurrency等を安全に確定できない。
- APPLYING / VERIFYING: operation intent保存後またはresponse後の中間状態。
- UNKNOWN_REMOTE_RESULT: timeout、切断、検証不能。blind retryしない。
- PARTIAL_APPLIED: description/commentの片方だけ確認。古いsnapshotで自動rollbackしない。
- APPLIED: descriptionと完全一致する公開comment（comment-onlyでも同じ）をremoteで確認しreceipt保存済み。
- NO_CHANGE: remote stateを変更せずproposalを完了。

## Recovery

`pending`で未完了を一覧し、`show`と`history`で現在revisionとoperation IDを確認する。
PENDING_PERMISSIONは許可後に`revalidate`、stale baseはAgentが最新descriptionで新しいsemantic mergeを
作って新proposalにし、旧proposalをsupersedeする。

UNKNOWN_REMOTE_RESULT/PARTIAL_APPLIED/APPLYING/VERIFYINGは `reconcile` で固定marker、payload hash、
description hashを照合する。結果が確認できても、snapshot不足ならAPPLIEDにしない。確認できない場合も
同じwriteを再送しない。

artifact作成後・SQLite commit前のcrashでorphanが検出された場合、通常openは安全停止する。内容を
確認したうえで `recover-local --reason ...` を明示実行すると、orphanをworkspace内のprivateな
`recovery/<recovery-id>/` へ移し、削除せずに監査を再実行する。DBが参照するartifactの欠落や改ざんは
自動復元せず、backupと人間の判断を必要とする。

起動監査はrevision artifact hashに加え、approvalと対象revision hash、APPLIED proposalとimmutable
receiptを照合する。receipt保存後・APPLIED遷移前に停止したVERIFYING proposalでは、receiptを証拠として
保持したまま`reconcile`する。`recover-local`とproposal/revision作成はworkspace lockで直列化する。

local lockは同一machine/workspace/targetのapplyを直列化するだけで、複数PCや複数userの協調、remote CAS、
exactly-onceを保証しない。pre-read直後の外部更新を排除できない。
