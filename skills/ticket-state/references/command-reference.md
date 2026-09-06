# コマンドリファレンス

この文書は、`ticket-state` CLIを直接実行するときの引き方をまとめる。初回のconfig作成、repository
binding、API keyのexportがまだなら、先に[初回セットアップ](getting-started.md)を完了する。

## 基本形

以下の例では、Skillの場所をshell変数へ入れている。

```bash
ticket_state_skill_dir="${HOME}/.agents/skills/ticket-state"
```

CLIは次の形で実行する。`--config`、`--work-dir`、`--workspace-id`、`--json`などのglobal optionは、
必ずsubcommandより前へ置く。

```text
python3 <Skill directory>/scripts/ticket_state.py [global options] <command> [command options]
```

たとえば、JSONでticketを読む場合は次の順序になる。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  read --ticket TEST-1
```

`proposal-id`は`prepare`、`update-state`、`snapshot`、`append-comment`が返すIDである。分からない場合は
`pending`で確認する。例中の`TEST-1`、`123`、path、hash、承認者名は実際の値へ置き換える。

## Global options

| Option | 用途 | 既定値・注意点 |
|---|---|---|
| `--config PATH` | 読み込むtrusted configを指定 | `${XDG_CONFIG_HOME}/agent-skills/ticket-state/config.toml` |
| `--work-dir PATH` | workspaceを置く親directoryを指定 | `${XDG_STATE_HOME}/agent-skills/ticket-state` |
| `--workspace-id ID` | 利用する状態workspaceを明示 | repository bindingより優先。`--work-dir`の下に追加される |
| `--json` | machine-readableなJSONで出力 | state、outcome、mutation件数の確認に推奨 |
| `--fixture PATH` | 同梱fixtureでGETを再現 | public eval専用。通常運用やwrite simulationには使わない |
| `--version` | CLI versionを表示 | subcommandは不要 |

`--profile`はglobal optionではなく、`read`と`template extract`だけが持つcommand optionである。
requestを受け取るコマンドでは、profileはrequest JSONかrepository bindingから解決する。

## 目的別早見表

「Remote write」はprovider APIへdescriptionやcommentの変更requestを送る可能性を表す。
`--dry-run`を付けた場合は常に0件になる。

| Command | 主な目的 | Remote read | Remote write | Local state更新 |
|---|---|---:|---:|---:|
| `context` | 現在のcloneに対応するprofile/workspaceを確認 | なし | なし | なし |
| `read` | 最新ticketを取得 | あり | なし | なし |
| `prepare` | proposalとdiffを保存 | あり | なし | あり |
| `update-state` | descriptionとsnapshotを計画・反映 | あり | あり | あり |
| `snapshot` | snapshot commentだけを計画・反映 | あり | あり | あり |
| `append-comment` | 指定commentだけを計画・反映 | あり | あり | あり |
| `pending` / `show` / `diff` / `history` | 保存済みproposalを調べる | なし | なし | なし |
| `approve` | revision/hashへの人間の承認を記録 | なし | なし | あり |
| `revalidate` | 最新baseとpermissionを再確認 | あり | なし | あり |
| `apply` | 保存済みproposalを再検証して反映 | あり | あり | あり |
| `reconcile` | 結果不明・部分成功をremote evidenceと照合 | あり | なし | あり |
| `reject` / `supersede` | proposalを処理済みに分類 | なし | なし | あり |
| `recover-local` | orphan artifactを隔離して再監査 | なし | なし | あり |
| `template extract` | 既存ticketから候補を生成 | あり | なし | あり |
| `template validate` | template artifactを検証 | なし | なし | なし |
| `template approve` | 確認済みcandidateをapproved artifact化 | なし | なし | あり |

## よく使う安全な流れ

Descriptionとsnapshotを更新する場合は、通常は次の順で進める。

```text
context → pending → read → update-state --dry-run → diff/show → apply
```

1. `context`で、このcloneに紐づくprofileとworkspaceを確認する。
2. `pending`で、同じworkspaceに処理途中のproposalがないか確認する。
3. `read --ticket ...`で、更新対象の最新descriptionとcommentsを取得する。
4. Agentが最新内容からrequest JSONを作り、`update-state ... --dry-run`でproposalを保存する。
5. 返されたproposal IDを`diff`と`show`へ渡し、対象、変更内容、revision/hash、permissionを確認する。
6. 同じproposal IDを`apply`へ渡す。終了後は`APPLIED`とremote evidenceが確認されたかを調べる。

Commentだけなら手順4の`update-state`を`snapshot`または`append-comment`へ置き換える。案の保存までで
止めるなら`prepare`を使い、remoteの反映結果が不明なら`apply`を繰り返さず`reconcile`へ進む。

## 接続先と対象を確認する

### `context`

現在directoryのGit rootに完全一致するrepository bindingから、binding名、profile、workspace IDを表示する。
remote APIへ接続せず、API keyも不要である。絶対pathやconfig pathは出力しない。

```bash
cd /home/YOU/work/monorepo-profile-a
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" --json context
```

bindingがない場合は安全停止する。`context`は`--profile`を受け取らないため、明示profileの疎通確認には
次の`read --profile ...`を使う。

### `read`

最新descriptionと公開comments/journalsを取得する。remoteを変更せず、proposalも作らない。

Repository bindingからprofileを選ぶ場合:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  read --ticket TEST-1
```

Profileを明示する場合:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  read --profile backlog_test --ticket TEST-1
```

Backlogでは通常`PROJECT-123`形式、Redmineでは数値issue IDを指定する。返却JSONにはticket本文が含まれる
ため、公開ログやissueへそのまま貼らない。

## 更新案を作る

Request JSONは[`assets/proposal.schema.json`](../assets/proposal.schema.json)に従う。基本例は
[`examples/update-state.request.json`](../examples/update-state.request.json)にある。
Requestの`operation`と実行するcommandは一致させる。repository bindingがある場合だけ`profile`を省略
できるが、`ticket`は常に明示する。

### `prepare`

最新remoteを読み、requestを検査し、proposal、revision、diff、予定payloadをlocalへ保存する。
permissionがあってもremote mutationは送らない。「案を保存して後で判断する」ときに使う。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  prepare --request /private/requests/update-test-1.json
```

結果が`READY`なら`diff <proposal-id>`で内容を確認し、反映時は`apply <proposal-id>`を使う。
`PENDING_PERMISSION`でも案は保存されている。

### `update-state`

Description全文とCurrent State Snapshot commentを同じproposalとして扱う。`--dry-run`なしでは、計画後に
permissionと鮮度を再検証し、条件を満たせばremoteへ反映する。

最初にpreviewする場合:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  update-state --request /private/requests/update-test-1.json --dry-run
```

確認後に新たな実行として計画・反映する場合:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  update-state --request /private/requests/update-test-1.json
```

Dry-runで作られたproposalを反映したい場合は、同じrequestを再実行するのではなく、返されたIDを
`apply <proposal-id>`へ渡す。`--dry-run`でもremote GETとlocal保存は行う。

### `snapshot`

Descriptionは変更せず、構造化されたCurrent State Snapshot commentだけを追加する。Requestの
`operation`は`snapshot`とし、`change_summary`、`snapshot`、`snapshot_description_sha256`を含める。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  snapshot --request /private/requests/snapshot-test-1.json --dry-run
```

実際に投稿するときだけ`--dry-run`を外す。必要permissionは`comment:append`である。

### `append-comment`

Requestの`comment`に書いた補足commentだけを追加する。Snapshot形式へ変換せず、descriptionも変更しない。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  append-comment --request /private/requests/comment-test-1.json --dry-run
```

Requestの`operation`は`append-comment`とする。実際に投稿するときだけ`--dry-run`を外す。

## 保存済みproposalを確認する

以下のコマンドはremote APIへ接続しない。repository bindingがないdirectoryから実行する場合や、別cloneの
workspaceを確認する場合は、対象を取り違えないよう`--workspace-id`を明示する。

### `pending`

未完了のproposalを一覧する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  pending
```

### `diff`

指定proposalのdescription diff、comment diff、予定comment全文、必要permissionを表示する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  diff 0123456789abcdef
```

本文を読みやすいtext形式で確認する用途に向く。機械処理する場合はsubcommandより前に`--json`を加える。

### `show`

現在state、対象identity、current revision、content hash、current revisionに有効な承認を表示する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  show 0123456789abcdef
```

`approve`する前は、ここでcurrent revisionと`content_sha256`を確認する。

### `history`

Proposal IDを指定すると1件、指定しないとworkspace全体のappend-only event historyを表示する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  history 0123456789abcdef
```

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  history
```

## 承認・再検証・反映

### `approve`

人間が確認した特定revisionと全artifactのcontent hashへの承認をlocal historyへ記録する。Remoteへの
write permissionを追加するコマンドではなく、別revisionへ承認を自動継承しない。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  approve 0123456789abcdef \
  --revision 1 \
  --content-sha256 aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa \
  --approved-by mahcialet \
  --reason "diffと公開範囲を確認済み"
```

### `revalidate`

保存済みproposalについて、現在のpermission、最新remote base、content境界を再確認する。Remote mutationは
送らない。Allowlistを変更した後や、DRAFT/PREPAREDからの再開に使う。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  revalidate 0123456789abcdef
```

結果が`NEEDS_REMERGE`なら、古いproposalをそのままapplyせず、最新descriptionを基に新しいsemantic mergeを
作る。

### `apply`

保存済みproposalを最新remoteと現在のallowlistで再検証し、条件を満たす場合だけ反映する。

反映直前の確認:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  apply 0123456789abcdef --dry-run
```

実際の反映:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  apply 0123456789abcdef
```

`--dry-run`は再検証結果をhistoryへ保存するが、remote mutationを0件にする。実行後は`outcome`、`state`、
`remote_mutation_requests`を確認する。

## 異常時とproposalの整理

### `reconcile`

`UNKNOWN_REMOTE_RESULT`、`PARTIAL_APPLIED`、`APPLYING`、`VERIFYING`のproposalを、保存済みoperation
marker、payload hash、最新remote evidenceと照合する。同じwriteをblind retryしない。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  reconcile 0123456789abcdef
```

このコマンド自身はremoteへwriteを送らない。結果が確定しない場合は、履歴とremote evidenceを保持して
人間の判断へ戻す。

### `reject`

採用しないproposalを`REJECTED`へ分類し、artifactと履歴は残す。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  reject 0123456789abcdef --reason "方針変更により採用しない"
```

### `supersede`

新しいproposalへ置き換えた古いproposalを`SUPERSEDED`へ分類し、artifactと履歴は残す。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  supersede 0123456789abcdef --reason "最新descriptionで再mergeしたproposalへ置換"
```

`reject`と`supersede`はlocal分類だが、現行CLIではtrusted configの読み込みが必要である。

### `recover-local`

Crash後に残ったorphan artifactを削除せず、同じworkspaceの`recovery/`へ隔離して再監査する。通常openが
orphan検出で停止し、内容を確認した後だけ使う。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  recover-local --reason "crash後のorphanを確認し隔離"
```

DBが参照しているartifactの欠落や改ざんを直すコマンドではない。その場合はbackupと人間の判断が必要に
なる。

## Template lifecycle

### `template extract`

指定した既存ticketだけを読み、共通構造のlocal candidateを作る。Ticketはspace区切りで1件以上指定する。
Candidateは自動採用されない。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  template extract --profile backlog_test --tickets TEST-1 TEST-2 TEST-3
```

Repository bindingを使う場合は`--profile`を省略できる。1件だけならevidence不足、順序が揃わなければreview
待ちになることがある。

### `template validate`

Candidateまたはapproved template artifactのschemaと内容をlocalで検証する。Config、API key、workspaceは
不要である。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  template validate --file /private/templates/candidate.json
```

Approved artifactだけを受け入れる検査:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  template validate \
  --file /private/templates/approved.json \
  --require-approved
```

成功時に返る`artifact_sha256`を、profileのtemplate設定とrequestの`template_sha256`へ固定する。

### `template approve`

人間が内容、用途、例外を確認したcandidateを、別のimmutable approved artifactとしてworkspaceへ保存する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id monorepo-profile-a \
  --json \
  template approve \
  --candidate /private/templates/candidate.json \
  --approved-by mahcialet \
  --reason "対象projectの標準構造として確認済み"
```

## 結果と終了code

Automationではexit codeだけで反映成功と判断せず、JSONの`outcome`、`state`、
`remote_mutation_requests`を確認する。

| Exit code | 主な意味 | 次の確認 |
|---:|---|---|
| `0` | 実行完了、`DRY_RUN`、`APPLIED`、`NO_CHANGE`、またはlocal確認成功 | JSONのstate/outcomeが目的と一致するか |
| `2` | `PENDING_PERMISSION`、`NEEDS_REVIEW`、`NEEDS_REMERGE`、設定・入力・usage error | stderrのerror、必要permission、最新baseを確認 |
| `3` | `UNKNOWN_REMOTE_RESULT`、`PARTIAL_APPLIED`、`FAILED`、反映途中state | 再送せず`show`、`history`、`reconcile`で確認 |

主なstateの意味と復旧手順は[state and recovery](state-and-recovery.md)を参照する。

## Helpを表示する

全commandの一覧:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" --help
```

個別commandのoption:

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" apply --help
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" template extract --help
```
