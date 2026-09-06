# Workflow

## Ticket targetの解決

Agentは次の優先順位でticket targetを決め、CLIとrequestには解決済みの値を必ず明示する。

1. ユーザーが今回の依頼で明示したticket ID。
2. ユーザーが指定した、または今回の作業の正本として実際に参照中のdesign doc、implementation plan、
   task documentにある単一で明示的なtarget metadata。
3. どちらにも一意な値がなければ、人間へ確認する。

文書から解決できるのは、`Ticket: TEST-1`、frontmatterの`ticket: TEST-1`、
`Redmine issue: 123`、`# TEST-1 認証設計`のように、metadata fieldまたは文書titleでその文書自体の対象だと
明示された値が1件だけの場合である。関連・親・子ticketの一覧、例示、変更履歴、自由記述中の単なる言及は
target metadataとして扱わない。文書間で値が競合する場合や、1文書に複数targetがある場合も選ばずに
確認する。

Branch名、commit message、Git remote、repository名、作業内容からの連想、repository全体のticket ID検索は
targetの根拠にしない。Repository bindingが解決するのはprofileとworkspaceだけである。Remote write前の
報告には解決したticketを含め、利用者が取り違えに気づけるようにする。

この解決規則は、design doc等の適切な場所に既に記録されたticket番号をAgentが再利用できるようにする
人間の明示要求に基づく。Local corpusの頻出形式を一般化したruleではない。対象metadataとして認める形式や
優先順位を広げる変更には、支持例、反例、境界例と人間のreviewを必要とする。

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
