# Recovery examples

## Stale proposal

`apply`の直前readでbase hashが変わった場合はNEEDS_REMERGEになる。保存済み本文を送らず、最新本文、
stale案、変更sectionをAgentが意味比較する。新proposalを作った後、旧proposalを
`supersede <id> --reason ...` で分類する。

## Unknown result

mutation送信後のtimeoutはUNKNOWN_REMOTE_RESULTになる。同じPUT/PATCHを再送せず、
`reconcile <id>` で固定operation markerとdescription hashを確認する。両方確認できた場合だけAPPLIED、
片方だけならPARTIAL_APPLIEDのまま人間へ返す。

## Read-only

allowlistに必要permissionがないproposalはPENDING_PERMISSIONで残る。target、diff、予定comment、理由、
必要permissionを人間へ示す。configを自動変更せず、許可後も`revalidate`する。

## Interrupted local state

proposal artifactとSQLite rowが揃ったDRAFTは`revalidate <id>`でPREPAREDから判定状態へ進める。
receipt保存後、APPLIED記録前に停止したproposalは同じmutationを再送せず`reconcile <id>`で確定する。
SQLite rowのないorphan artifactで起動監査が止まった場合だけ、理由を明示して`recover-local`を実行し、
削除ではなく`recovery/`へ隔離する。
