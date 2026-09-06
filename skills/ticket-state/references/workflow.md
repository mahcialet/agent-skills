# Workflow

## Readからproposalまで

1. trusted configからprofile、instance、project numeric ID、ticket identifierを解決する。profileが
   明示されていなければ、current Git rootとprivateなrepository bindingの完全一致から解決する。
   bindingがなければ既定profileを推測しない。
2. 設定済みendpointへ最小限のreadを行い、remoteのproject ID/keyを照合する。別projectの本文は
   Agentへ返さず、保存もしない。
3. Agentは取得した最新descriptionと明示された事実から、semantic merge後の全文、変更section、
   change summary、構造化snapshotを作る。runtimeは意味判断を文字列置換で代用しない。
4. plannerはbase、intent、proposed description、snapshot、comment、diff、hash、provider capabilityを
   immutable revisionへ保存する。SQLiteのproposal/state/historyが検索と再開の正本になる。

## Apply

applyはprofile/targetの再照合、最新read、base hash、現在のallowlist、strict concurrency、local lockを
順に確認する。remote mutation前にoperation IDとpayload hashをSQLiteへcommitする。network request中に
SQLite transactionは保持しない。

description更新とsnapshotは同じprovider requestへ含める。BacklogはPATCH form、RedmineはPUT JSON。
comments-only操作は専用POSTまたはnotes-only PUTを使う。status等のfieldは送らない。

成功responseだけでAPPLIEDにせず、最新descriptionと固定operation markerを再取得する。markerが
見つからないことを、取得範囲が不完全なまま「未反映」と断定しない。

## Dry-run

`--dry-run` はofflineではない。通常と同じresolver、reader、planner、policy、payload builderを使う。
local proposal/diff/historyを保存し、adapterのmutation boundaryへは到達しない。JSONの
`remote_mutation_requests` は0、`outcome` はDRY_RUNになる。ROならPENDING_PERMISSIONを保持する。

## Scope

関連・親・子ticketを自動更新しない。複数targetを使うtemplate抽出も明示リストのreadだけを行う。
ticket作成・削除、status、assignee、priority、期限、工数、添付、親子関係は対象外。
