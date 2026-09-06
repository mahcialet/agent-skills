# Recovery examples

## Stale proposal

`apply`の直前readでbase hashが変わった場合はNEEDS_REMERGEになる。保存済み本文を送らず、最新本文、
stale案、変更sectionをAgentが意味比較する。新proposalを作った後、旧proposalを
`supersede <id> --reason ...` で分類する。

serviceの確認後、adapterの送信直前readまでの間に本文やcontextが変わった場合も、更新0件で
NEEDS_REMERGEへ止める。その境界で設定済みsecretを検出した場合は、内容を保存せずFAILEDへ記録する。
送信していない拒否をAPPLYINGのまま残したり、送信後の結果不明と同一視したりしない。

## Unknown result

mutation送信後のtimeoutはUNKNOWN_REMOTE_RESULTになる。同じPUT/PATCHを再送せず、
`reconcile <id>` で固定operation markerとdescription hashを確認する。両方確認できた場合だけAPPLIED、
意図した変更の片方だけ確認できればPARTIAL_APPLIEDのまま人間へ返す。本文を変えないsnapshotで
コメントが見つからなければ、本文一致だけを反映の証拠にせずUNKNOWN_REMOTE_RESULTにする。
本文がbaseと同じupdate-stateでも同様である。変更した本文だけが一致する場合は部分反映の証拠になる。

送信後の確認readでproject/identity変更や設定済みsecretを検出した場合もUNKNOWN_REMOTE_RESULTとして
記録し、安全でない本文・例外詳細は保存しない。安全に読み取れる状態へ戻ってからreconcileし、再送せず
同じoperationの結果を確認する。送信前のidentity/secret検査失敗を反映済みと推測する規則ではない。

これらは反映結果の証拠に関するレビュー指摘に基づく修正例であり、local corpusからの一般化ではない。

## Read-only

allowlistに必要permissionがないproposalはPENDING_PERMISSIONで残る。target、diff、予定comment、理由、
必要permissionを人間へ示す。configを自動変更せず、許可後も`revalidate`する。

## Interrupted local state

proposal artifactとSQLite rowが揃ったDRAFTは`revalidate <id>`でPREPAREDから判定状態へ進める。
最初のprepareで入力hashが既にstaleだった場合は、その判断も復元してNEEDS_REMERGEを維持する。
NO_CHANGEだった場合も更新不要の判断を維持する。新鮮なremoteからbaseを保存したことだけを理由に、
古い入力本文をREADYへ昇格させない。
receipt保存後、APPLIED記録前に停止したproposalは同じmutationを再送せず`reconcile <id>`で確定する。
SQLite rowのないorphan artifactで起動監査が止まった場合だけ、理由を明示して`recover-local`を実行し、
削除ではなく`recovery/`へ隔離する。

receiptのidentity・本文hash・comment marker・comment ID・comment hashのいずれかが改変されていれば、
他のproposal/operation/payload値が一致していても監査は失敗する。正しいreceiptは中断後の照合に使えるが、
改変されたreceiptを自動修復して反映済みとはしない。
receipt保存後の中断から照合するとき、別comment等でremote_updated_atだけが変わっていても、本文と
operation commentの証拠が同じなら元のreceiptを再利用する。本文や対象commentが違う場合まで同一視しない。

既存の共有parentを`--work-dir`へ指定しても、そのpermissionは変更しない。新しいworkspace childは
0700で作成する。これらの境界例はPR #6のレビュー指摘に基づく回帰検証であり、local corpus由来の
新しい運用ルールではない。
