# Agentとの使い方

セットアップ後は、通常、`ticket_state.py`を手入力する必要はない。利用者はAgentへ「どのticketを、
どう扱い、どこまで進めるか」を伝え、Agentが`ticket-state` Skillと同梱CLIを選んで実行する。

初回は、接続先や公開範囲の取り違えに気づきやすいよう、読み取り、更新案の確認、適用を分けて試す。
一連の結果を確認できた後は、明示的な更新依頼を一度の会話で完了させてもよい。

## 依頼に含めるもの

依頼では、次の3点が分かればよい。

1. **対象ticket**: `TEST-1`やRedmineのissue IDなど。依頼に書かなくても、今回の作業対象として実際に
   参照しているdesign doc等に一意のtarget metadataがあればAgentが解決できる。
2. **してほしいこと**: 読み取り、descriptionとsnapshotの更新、snapshotだけ、補足commentだけ、など。
3. **今回の停止位置**: 読み取りだけ、更新案とdiffまで、remoteへの適用まで、のいずれか。

API key、config path、workspace ID、CLI command名は、通常の依頼へ書かなくてよい。API keyはAgentを
起動したshellの環境変数から渡される。

Design docに記載する場合は、関連ticketの一覧や自由記述中の言及と区別できる形にする。

```markdown
Ticket: TEST-1
```

Frontmatterを使う文書なら次でもよい。

```yaml
ticket: TEST-1
```

文書titleで対象を明示する形も使える。

```markdown
# TEST-1 認証処理の設計
```

対象が複数ある、複数文書で番号が競合する、関連ticketへの言及しかない場合はAgentが確認する。Branch名や
repository全体の検索結果からは選ばない。

## 初回に推奨する3段階

### 1. Contextと読み取りだけ確認する

最初はremoteを変更しないことを明示する。

```text
$ticket-stateを使って、現在のGit repositoryに紐づくcontextを確認し、
ticket TEST-1の最新descriptionと公開commentsを読み取ってください。
更新案の作成やremoteへの書き込みはしないでください。
```

Agentから、解決したprofile、workspace、ticket identity、読み取り結果が返ることを確認する。別project、
別ticket、想定外のproviderが表示された場合は先へ進まない。

### 2. 更新案とdiffまで作る

次に、remoteへ書かず、local proposalとdiffを保存する。

```text
$ticket-stateを使ってticket TEST-1の最新状態を読み、今回の作業結果を
descriptionとCurrent State Snapshotへ反映する更新案を作ってください。
GoalとConstraintsは変更しません。diffを見せるところまで進め、remoteへは適用しないでください。

今回の事実:
- 認証処理の実装が完了
- unit test 42件が成功
- live環境での確認は未実施
- 次はstagingでread-only疎通確認
```

Agentは最新remoteを基にrequestを組み立て、remote mutationを行わない方法でproposalを保存する。利用者は
結果のうち、少なくとも次を確認する。

- 対象profileとticket
- Descriptionと予定commentのdiff
- Proposal IDとcurrent revision
- `remote_mutation_requests`が`0`
- `READY`、`PENDING_PERMISSION`、`NEEDS_REVIEW`などのstate

記載事実、公開してよい範囲、Goal/Constraints、既存記述の保持に問題があれば、この段階でAgentへ修正を
依頼する。

### 3. 確認したproposalを適用する

Proposal IDを指定し、最新remoteとpermissionの再検証を含めて依頼する。

```text
$ticket-stateのproposal 0123456789abcdefについて、もう一度対象とdiffを確認し、
最新remoteと現在のpermissionを再検証してから適用してください。
結果のstate、remote mutation request数、remoteでの反映確認結果を報告してください。
```

Agentが`APPLIED`を返し、descriptionと公開commentをremoteから再取得して確認できたことを確認する。
`PENDING_PERMISSION`、`NEEDS_REMERGE`、`NEEDS_REVIEW`なら未反映であり、その理由を解消してから次へ進む。

## 慣れた後の依頼例

接続先、markup、公開範囲、allowlistの動作を確認できた後は、コマンドを意識せずに依頼できる。

### 最新状態を読む

作業中のdesign docにtarget metadataがある場合:

```text
$ticket-stateで、このdesign docに紐づくticketの最新状態を読んで、現在地と未解決事項をまとめてください。
チケットは更新しないでください。
```

Ticketを直接指定する場合:

```text
$ticket-stateでTEST-1の最新状態を読んで、現在地と未解決事項をまとめてください。
チケットは更新しないでください。
```

### Descriptionとsnapshotを更新する

```text
$ticket-stateでTEST-1を最新状態に更新してください。
今回完了したのは認証処理とunit testで、live検証はまだです。
GoalとConstraintsは変えず、既存の他者の記述を保持してください。
適用結果とremoteでの確認結果まで報告してください。
```

「更新してください」はremote反映までを求める依頼になる。Previewだけが必要なら「更新案とdiffまで。
remoteへは適用しない」と明記する。

### Snapshotだけを追加する

```text
$ticket-stateでTEST-1へCurrent State Snapshotだけを追加してください。
descriptionは変更しないでください。内容は公開commentとして扱ってよい情報だけです。
```

### 補足commentだけを追加する

```text
$ticket-stateでTEST-1へ次の補足commentだけを追加してください。
descriptionやsnapshotは変更しないでください。

staging環境の停止時間は9月10日18:00-19:00です。
```

### 更新案を保存して引き継ぐ

```text
$ticket-stateでTEST-1の更新案とdiffを作り、remoteへは適用せず保存してください。
権限が不足していてもproposal ID、必要permission、再開方法を報告してください。
```

### 既存ticketからtemplate候補を作る

`template extract`が作るのは、ticket本文を複製した雛形ではない。指定したticketから見出し、順序、
構造上の例外、evidence hashを抽出したlocal candidateである。Candidateは自動承認されず、remoteも
更新しない。

共通構造を調べる場合は、複数の代表的なticketを指定する。

```text
$ticket-stateでTEST-1、TEST-2、TEST-3を読み、template candidateを作ってください。
共通見出し、順序の違い、例外、candidateの保存先を報告してください。
remoteの更新とtemplateの承認はしないでください。
```

正式な原型が1件だけ決まっている場合もcandidateを作成できる。ただし、sampleが1件なら結果は
`NEEDS_MORE_EVIDENCE`になる。内容、用途、例外を人間が確認した後だけ、別の依頼で承認する。

## 依頼とAgent内部のcommand対応

利用者がcommand名を指定する必要はないが、Agentの動きを確認したい場合は次を目安にする。

| 利用者の依頼 | Agentが主に使うcommand | Remote write |
|---|---|---:|
| Context確認 | `context` | なし |
| 最新状態を読むだけ | `read` | なし |
| 更新案を保存しdiffまで | `prepare`または`--dry-run` | なし |
| Descriptionとsnapshotを更新 | `update-state` | あり |
| Snapshotだけを追加 | `snapshot` | あり |
| 補足commentだけを追加 | `append-comment` | あり |
| 保存済み案を確認 | `pending`、`show`、`diff`、`history` | なし |
| 保存済み案を適用 | `apply` | あり |
| Permissionや最新baseだけ再確認 | `revalidate` | なし |
| 結果不明・部分成功を調査 | `reconcile` | なし |

全commandの引数やlocal stateへの作用は[コマンドリファレンス](command-reference.md)を参照する。

## Agentの報告で確認すること

書き込みを伴う依頼では、終了codeだけでなく次の報告を確認する。

| 項目 | 確認内容 |
|---|---|
| 対象 | 想定したprovider、profile、project、ticketか |
| Mode | read-only、dry-run、実適用のどれか |
| Proposal | Proposal IDとcurrent revisionは何か |
| Diff | Descriptionと公開commentへ何が追加・変更されるか |
| Permission | 必要permissionと不足permissionは何か |
| Remote request | `remote_mutation_requests`は想定件数か。Previewなら`0`か |
| Result | `APPLIED`、`NO_CHANGE`、未反映、結果不明のどれか |
| Verification | Remoteを再取得して反映を確認できたか |

`PENDING_PERMISSION`は「案を保存したが書いていない」、`NEEDS_REMERGE`は「remoteが変わったため古い案を
送っていない」、`UNKNOWN_REMOTE_RESULT`は「反映有無を断定できない」を意味する。詳しくは
[state and recovery](state-and-recovery.md)を参照する。

## 初期に起きやすい混乱

### Ticket番号を毎回入力する必要があると思ってしまう

今回の作業対象として実際に参照しているdesign doc等に`Ticket: TEST-1`のような単一のtarget metadataが
あれば、Agentはその値を使える。ユーザーの依頼に別の番号があればそちらを優先する。

Repository bindingが選ぶのはprofileとworkspaceだけであり、ticketではない。Branch名、関連ticketの一覧、
例示、repo全体の検索結果からは選ばず、一意に解決できなければAgentが確認する。

### 「確認して」が更新依頼として扱われると思ってしまう

読み取り、確認、要約だけの依頼はremote writeを許可しない。更新案が欲しい場合は「更新案とdiffまで」、
実際に反映したい場合は「適用まで」と停止位置を伝える。

### Dry-runなら何も保存されないと思ってしまう

Dry-runはremote mutationを0件にするが、最新remoteのGETとlocal proposal、diff、historyの保存は行う。
保存済みproposalは`pending`で確認できる。

### Allowlistを設定しただけで自動更新されると思ってしまう

Allowlistは実行を許可する条件であり、自動実行の設定ではない。過去のdry-runも自動適用されない。利用者の
更新依頼を受けたAgentが、最新remoteとpermissionを再検証して初めてwriteへ進む。

### Timeout後に同じ更新を頼み直してしまう

`UNKNOWN_REMOTE_RESULT`や`PARTIAL_APPLIED`では、同じwriteを再送しない。Agentへ「proposal IDを
`reconcile`して」と依頼し、remote evidenceから結果を照合する。

```text
$ticket-stateのproposal 0123456789abcdefが結果不明です。
再送せず、remote evidenceとreconcileして現在のstateを報告してください。
```

### Private noteの内容を公開snapshotへ混ぜてしまう

Ticket-stateが追加するsnapshot/commentは公開commentとして扱う。公開してよい情報だけを渡し、private
noteや非公開会話を根拠に含めない。判断できない場合は、Agentへremote適用せず停止するよう依頼する。
