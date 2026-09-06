# State and recovery

## 保存構造

状態は配布Skillやtrusted configと分離し、privateなworkspaceに保存する。
DRAFT/PREPAREDからの復旧でも、最初の入力hash不一致によるNEEDS_REMERGEやNO_CHANGEの判断を失わない。
保存baseがfreshでも入力本文がstaleだった事実を消さず、古い本文をREADYへ昇格させない。
`--work-dir`はparent directoryであり、既存parentのpermissionを変更しない。CLIが作成するparentと
workspace childは0700にする。

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

人間のcontent approvalを記録する場合はproposal ID、revision、全artifactのcontent hash、時刻、
確認内容の要約へbindingする。名前は必須ではなく、省略時の`conversation-user`は会話上の役割である。
確認を別revisionへ自動継承せず、write permissionの
代わりにも使わない。監査metadataはprivate workspaceに保持し、公開本文・コメントやリポジトリへ転載しない。

## State

- DRAFT / PREPARED: artifact保存済みの準備段階。DRAFTで中断した場合は`revalidate`で再開する。
- READY: apply前の全local gateを通過。
- PENDING_PERMISSION: 必要permission不足。remote mutation 0。
- NEEDS_REMERGE: remote baseが変化。古いproposalのapprovalは再利用しない。
- FAILED: 明確なremote失敗、または送信直前の安全検査による拒否。secret検出時は安全な理由だけを記録する。
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
serviceのpre-readとadapterの送信直前readの間でcontextが変わった場合も、更新0件でstale revisionを
保存しNEEDS_REMERGEへ進む。送信直前のsecret検出はFAILEDで停止し、APPLYINGを残さない。

UNKNOWN_REMOTE_RESULT/PARTIAL_APPLIED/APPLYING/VERIFYINGは `reconcile` で固定marker、payload hash、
description hashを照合する。結果が確認できても、snapshot不足ならAPPLIEDにしない。確認できない場合も
同じwriteを再送しない。
送信後のidentity不一致・secret検出で確認readを安全に扱えない場合もUNKNOWN_REMOTE_RESULTへ記録する。
本文が元から同じだけでは部分反映の証拠にしない。PARTIAL_APPLIEDには、変更した本文または送信した
コメントの一致が必要である。

artifact作成後・SQLite commit前のcrashでorphanが検出された場合、通常openは安全停止する。内容を
確認したうえで `recover-local --reason ...` を明示実行すると、orphanをworkspace内のprivateな
`recovery/<recovery-id>/` へ移し、削除せずに監査を再実行する。DBが参照するartifactの欠落や改ざんは
自動復元せず、backupと人間の判断を必要とする。

起動監査はrevision artifact hashに加え、approvalと対象revision hash、APPLIED proposalとimmutable
receiptを照合する。receipt保存後・APPLIED遷移前に停止したVERIFYING proposalでは、receiptを証拠として
保持したまま`reconcile`する。`recover-local`とproposal/revision作成はworkspace lockで直列化する。

receiptのidentity・本文hash・comment marker/hashをimmutable revisionの計画と照合し、comment IDを含む
非揮発の証拠全体は、receipt保存前にSQLiteへ記録した`REMOTE_RECEIPT_EVIDENCE`のhashとも照合する。
照合時刻・取得時刻・remote_updated_atは揮発値として再利用比較から除外する。別のcomment追加等で
更新時刻だけが進んでも、非揮発の証拠が同一なら元のreceiptを変更せずに再利用できる。
証拠の改変・欠落を、既存receiptから新しいhashを作って自動的に正当化しない。

この監査強化より前に保存されたreceiptには独立した証拠hashがないため、監査は安全停止する。
旧workspaceはprivateな履歴として保管し、新規操作には新しいworkspace IDを使う。完了済み操作を
新workspaceから再送しない。旧形式の自動移行や既存履歴の削除は行わない。

local lockは同一machine/workspace/targetのapplyを直列化するだけで、複数PCや複数userの協調、remote CAS、
exactly-onceを保証しない。pre-read直後の外部更新を排除できない。
