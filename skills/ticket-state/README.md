# ticket-state

BacklogまたはRedmineのチケットdescriptionを共有された現在地として読み、更新できる場合は
descriptionとCurrent State Snapshotコメントを反映し、書けない場合もproposalとdiffを失わずに
保存するSkillです。CodexとGitHub Copilot CLIは同じ `SKILL.md` と同じPython CLIを使います。

## 実装状態

- 実装済み: trusted config、project/instance/ticket identity、ticket単位allowlist、read、proposal、
  immutable revision、SQLite history、diff、dry-run、combined update、再取得検証、revalidate、
  reconcile、template candidate/approval分離、template未設定時の内蔵default。
- mock検証済み: BacklogとRedmineのread/update/comment、RO、dry-run、stale base、permission取消、
  timeout後のreconcile、partial result、process間local concurrency、secret非URL送信、Redmineの
  `private_notes: false`、中断後のDRAFT/receipt復旧、local artifact/DB破損検出。
- live検証済み: 非公開の閉域テスト環境上のRedmine 2.6.10～7.0.1（各minor系列）で、HTTPS read、
  permission gate、dry-run、公開comment、descriptionとsnapshotの更新、stale base拒否。
- 未検証: 実Backlog、実運用instance固有のplugin・proxy・visibility・上限、複数PC間の協調、
  server-side CAS。live credentialsや実運用チケットへの接続はこのリポジトリに含みません。

## 必要環境

Python 3.12以降の標準ライブラリだけを使います。起動時にpackageをinstallしません。

```bash
python3 scripts/ticket_state.py --help
python3 scripts/validate_content.py
```

## 設定と状態

`assets/config.example.toml` をrepo外のprivateな場所へコピーし、実値を設定します。

- 既定設定: `${XDG_CONFIG_HOME:-~/.config}/agent-skills/ticket-state/config.toml`
- 既定状態: `${XDG_STATE_HOME:-~/.local/state}/agent-skills/ticket-state/<workspace-id>/`
- 明示指定: `--config`、`--work-dir`、`--workspace-id`

API keyは `api_key_env` が指す環境変数だけから読みます。値をTOML、CLI引数、request、proposal、
diff、ログへ書かないでください。project内の `--work-dir` はGitでignore済みの場合だけ使えます。
状態directoryとartifactはprivate permissionで作成されます。同じOS userがconfig・コード・環境変数を
変更できる場合、CLIは強制的なsecurity boundaryではありません。

実キーを使わないpublic CLI evalでは `--fixture examples/fixtures/backlog.json` を指定できます。
fixture transportはmanifestに完全一致するHTTPS GETだけを返し、mutationを常に拒否します。通常運用の
offline cacheやwrite simulationとして使わないでください。

## Request

`examples/update-state.request.json` を参照してください。`visibility_confirmed: true` と
`source_visibility: public-only` は、private note等を意図せず公開しないための明示的な確認です。
Goal/Constraintsを変更する場合は `protected_change_approval` に人間のreviewerと理由が必要です。
templateを使う場合は、profileの `template` とrequestの `template_id` に承認済み32文字IDを指定し、
`template validate` が返す `artifact_sha256` をrequestの `template_sha256` に固定します。candidateや
hash不一致のtemplateは更新へ使えません。

profileにtemplateがなく、空のdescriptionを更新する場合は、確認した記法に対応する
`assets/default-ticket.*.txt`を使います。内容があるdescriptionの構造追加には明示指示を必要とし、
既存構造はdefaultへ自動変換せず、明示templateの不備をdefaultで迂回しません。適用条件とplaceholderは
`references/templates-and-merge.md`を参照してください。

## Commands

```text
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

人間が特定diffを承認する場合、`show`のcurrent revisionと`content_sha256`を確認し、
`approve <proposal-id> --revision <n> --content-sha256 <hash> --approved-by <name> --reason <reason>`
で記録します。承認はwrite permissionの代わりではありません。再mergeでrevision/hashが変わると、旧承認は
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
