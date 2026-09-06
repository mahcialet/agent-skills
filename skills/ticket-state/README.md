# ticket-state

BacklogまたはRedmineのチケットdescriptionを共有された現在地として読み、更新できる場合は
descriptionとCurrent State Snapshotコメントを反映し、書けない場合もproposalとdiffを失わずに
保存するSkillです。CodexとGitHub Copilot CLIは同じ `SKILL.md` と同じPython CLIを使います。

## 実装状態

- 実装済み: trusted config、project/instance/ticket identity、ticket単位allowlist、read、proposal、
  immutable revision、SQLite history、diff、dry-run、combined update、再取得検証、revalidate、
  reconcile、template candidate/approval分離、template未設定時の内蔵default、privateなrepository
  rootからのprofile/workspace解決。
- mock検証済み: BacklogとRedmineのread/update/comment、RO、dry-run、stale base、permission取消、
  timeout後のreconcile、partial result、process間local concurrency、secret非URL送信、Redmineの
  `private_notes: false`、中断後のDRAFT/receipt復旧、local artifact/DB破損検出。
- live検証済み（Backlog API v2、サービスversion未取得）: read、preview、権限・未確認時の停止、
  名前なしの確認記録、本文＋snapshot、snapshot単独、通常コメント、本文復元、NO_CHANGE、
  template抽出・検証。HTTP 429発生後は待機して本文復元まで完了した。
- live検証済み（Redmine）: 非公開の閉域テスト環境上のRedmine 2.6.10～7.0.1（各minor系列）で、HTTPS read、
  permission gate、dry-run、公開comment、descriptionとsnapshotの更新、stale base拒否。
- live未完了（Backlog）: 復元後の古い案の再検証と追加prepareは接続エラーで未完了。
  障害復旧用操作（reconcile / recover-local等）とtemplate承認は実機未実施。429後の待機・復元は、
  これらの復旧操作やrate limit全般の検証を意味しない。
- 未検証: 実運用instance固有のplugin・proxy・visibility・上限、複数PC間の協調、server-side CAS。
  Redmineの確認version一覧は[provider capabilities](references/provider-capabilities.md)を参照。
  live credentials・接続先・実環境の監査記録はこのリポジトリに含みません。

## 必要環境

Python 3.12以降の標準ライブラリだけを使います。起動時にpackageをinstallしません。

```bash
python3 scripts/ticket_state.py --help
python3 scripts/validate_content.py
```

## 設定と状態

設定と状態はrepo外へ置きます。初めて設定する場合は、configのコピー、Backlog/Redmine別の記入例、
read疎通確認、状態の確認、よくあるエラーを説明した
[初回セットアップ](references/getting-started.md)から進めてください。

セットアップ後は、通常、利用者がCLIを直接操作する必要はありません。Agentへ対象ticket、してほしいこと、
停止位置を自然言語で伝えます。初回の段階的な確認方法と依頼文の例は
[Agentとの使い方](references/using-with-agent.md)を参照してください。

Agent CLIを起動するshellから保存先とAPI keyをexportします。Bashでの最小例は次のとおりです。

```bash
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"

install -d -m 700 "${XDG_CONFIG_HOME}/agent-skills/ticket-state"
install -d -m 700 "${XDG_STATE_HOME}/agent-skills/ticket-state"

read -rsp 'Backlog API key: ' BACKLOG_API_KEY
printf '\n'
export BACKLOG_API_KEY

# export後の同じshellから起動すると、子processのAgent CLIへ環境変数が継承される
codex
```

既定の設定ファイルは`${XDG_CONFIG_HOME}/agent-skills/ticket-state/config.toml`、状態は
`${XDG_STATE_HOME}/agent-skills/ticket-state/<workspace-id>/`です。API keyの値はconfigへ書かず、
`api_key_env = "BACKLOG_API_KEY"`のように環境変数名だけを指定します。すでに起動中のAgent CLIには
後からexportした値が届かないため、一度終了して同じshellから起動し直してください。

同じGit remoteから複数directoryへcloneして別profileを使う場合は、同じprivateなconfig.tomlの
`[repositories.<name>]`へclone root、profile、workspace IDを登録します。Git remoteではなくlocal rootの
完全一致で選ぶため、cloneごとに別の接続先と状態を使えます。共有リポジトリの`AGENTS.md`やtracked
fileへ個人設定を追加する必要はありません。bindingがなければprofileを自動推測しません。

既定値を使わない場合は、`--config`、`--work-dir`、`--workspace-id`で明示的に上書きできます。指定方法は
[初回セットアップ](references/getting-started.md)で説明しています。

API keyをTOML、CLI引数、request、proposal、diff、ログへ書かないでください。project内の
`--work-dir`はGitでignore済みの場合だけ使えます。状態directoryとartifactには取得したticket本文も
保存されるため、privateな領域として扱ってください。同じOS userがconfig・コード・環境変数を変更
できる場合、CLIは強制的なsecurity boundaryではありません。

実キーを使わないpublic CLI evalでは `--fixture examples/fixtures/backlog.json` を指定できます。
fixture transportはmanifestに完全一致するHTTPS GETだけを返し、mutationを常に拒否します。通常運用の
offline cacheやwrite simulationとして使わないでください。

## Request

`examples/update-state.request.json` を参照してください。`visibility_confirmed: true` と
`source_visibility: public-only` は、private note等を意図せず公開しないための明示的な確認です。

current repositoryにbindingがある場合はrequestの`profile`を省略でき、CLIが解決した値をproposalへ
固定します。bindingがない場合は従来どおり`profile`が必須で、CLI requestの`ticket`は常に省略
できません。ユーザーが番号を指定していなくても、今回の作業対象として参照中のdesign doc等に単一の
`Ticket: TEST-1`のようなtarget metadataがあれば、Agentがそこから解決してrequestへ明示できます。
複数候補や関連ticketへの言及しかない場合は、Agentが確認せずに選びません。

Goal/Constraintsの変更も事前の承認者情報なしでpreviewを作れます。実反映前に具体的内容への確認を
current revisionへ記録します。Request内の`protected_change_approval`は廃止され、指定すると入力エラーに
なります。確認はpreview後の`approve`へ集約します。
templateを使う場合は、profileの `template` とrequestの `template_id` に承認済み32文字IDを指定し、
`template validate` が返す `artifact_sha256` をrequestの `template_sha256` に固定します。candidateや
hash不一致のtemplateは更新へ使えません。

profileにtemplateがなく、空のdescriptionを更新する場合は、確認した記法に対応する
`assets/default-ticket.*.txt`を使います。内容があるdescriptionの構造追加には明示指示を必要とし、
既存構造はdefaultへ自動変換せず、明示templateの不備をdefaultで迂回しません。適用条件とplaceholderは
`references/templates-and-merge.md`を参照してください。

## AgentとCLI commands

通常、利用者がcommand名を選ぶ必要はありません。Agentへの依頼と内部commandの対応は
[Agentとの使い方](references/using-with-agent.md)を参照してください。CLIを使った切り分けや、各commandの
remote read/write、引数、実行例が必要な場合は[コマンドリファレンス](references/command-reference.md)を
参照してください。

```text
context              current Git repositoryのprofileとworkspaceを解決
read                 最新ticketと必要なcomments/journalsを取得
prepare              remoteを読み、proposal/diffだけを保存
update-state         description + snapshotを計画・反映
diff                 保存済みdiffと予定コメントを表示
apply                保存済みrevisionを再検証して反映
snapshot             snapshotコメントだけを計画・反映
append-comment       明示コメントだけを計画・反映
pending              未反映proposal一覧
show                 proposal/revision metadata
history              append-only event history
approve              proposal revision/artifact hashへの人間の承認を記録
recover-local         crashで残ったorphan artifactを削除せず隔離して再監査
revalidate           permissionとremote baseを再確認
reconcile            結果不明/部分成功をremote evidenceで照合
reject / supersede   履歴を消さずに処理済み分類
template extract     local candidateのみ生成
template validate    candidate/approved artifactを検証
template approve     人間確認済みcandidateを別artifactへ固定
```

`update-state`、`apply`、`snapshot`、`append-comment` の `--dry-run` はremote mutationを0件に
します。必要なGETは実行し、local proposal、diff、予定payload、historyは保存します。
dry-run後にallowlistが変わっても自動適用されません。

Agentが対象と更新内容を示し、利用者は「はい」だけで確認できます。同じ具体的操作への許可が既にあれば
重複確認しません。Agentが提示前に`show`のrevisionと`content_sha256`を保持し、返答後も同じ値であることを
確認してから、その提示済みの値で
`approve <proposal-id> --revision <n> --content-sha256 <hash> --reason <summary>`
でprivate履歴へ記録します。名前の入力は不要です。`--approved-by`は任意で
残し、省略時の`conversation-user`は会話上の役割を表します。確認者情報は公開payloadに含めません。
承認はwrite permissionの代わりではありません。再mergeでrevision/hashが変わると、旧承認は
履歴に残りますがcurrent revisionの承認として表示されません。

## Stateと終了結果

- `APPLIED`: descriptionと完全一致する公開snapshot/commentを再取得し、receiptとの対応も監査済み。
- `NO_CHANGE`: descriptionと宣言されたstateのどちらも不変。コメントは追加しない。
- `PENDING_PERMISSION`: local proposalはあるが必要permissionがない。
- `NEEDS_REMERGE`: baseが古い。新しいsemantic mergeが必要。
- `NEEDS_REVIEW`: strict concurrencyやcontent境界を安全に確定できない。
- `UNKNOWN_REMOTE_RESULT`: timeout等で反映有無が不明。blind retry禁止。
- `PARTIAL_APPLIED`: description/commentの一部だけ確認。自動rollback禁止。
- `FAILED`: remoteが明確に失敗。原因を解消して再検証する。

JSONの `would_write` は、現在のproposalが `READY` で、現在のallowlistが必要permissionを満たす場合
だけtrueです。`APPLIED`、結果不明、部分成功、失敗、手動分類済みのproposalを再送可能という意味には
使いません。

JSONの `outcome`、`state`、`remote_mutation_requests` を見て判断し、exit 0だけをAPPLIEDの証拠に
しないでください。詳細は `references/state-and-recovery.md` にあります。

## Security

adapterは設定済みHTTPS origin/subpathだけへ接続し、redirectを追いません。Backlogは
`Backlog-API-Key`、Redmineは `X-Redmine-API-Key` headerを使い、API keyをURLへ入れません。
取得したJSON全体を更新APIへ送り返さず、description/commentに限定してserializeします。

## Licenseと出典

リポジトリとSkillはMIT Licenseです。API契約の参照先と由来は `NOTICE.md` を参照してください。
