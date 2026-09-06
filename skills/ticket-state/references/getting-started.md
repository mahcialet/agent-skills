# 初回セットアップ

この手順では、ticket-state Skillをインストール済みのBash環境で、設定と状態をrepo外へ置き、
API keyをファイルへ保存せずにAgent CLIへ渡す。最初の疎通確認はreadだけを実行し、remoteを更新しない。

## 1. 読み込みの流れ

環境変数は、exportしたshellから後で起動したprocessへ継承される。

```text
Bashでexport
└── Agent CLI
    └── ticket-state Python CLI
        ├── XDG_CONFIG_HOMEからconfig.tomlを読む
        ├── current Git rootからprofileとworkspaceを解決する
        ├── configのapi_key_envが指す環境変数からAPI keyを読む
        └── XDG_STATE_HOMEへproposal、diff、historyを保存する
```

すでに起動しているAgent CLIや、desktop launcherから起動したprocessには、現在のshellで後から
exportした値は届かない。その場合はAgent CLIを終了し、exportした同じshellから起動し直す。

## 2. Skillの場所を確認する

user scopeの標準配置を使う例では、Skillは`~/.agents/skills/ticket-state`にある。次の変数は手動確認用
コマンドを短くするためのshell変数であり、ticket-state自体が読む設定ではない。

```bash
ticket_state_skill_dir="${HOME}/.agents/skills/ticket-state"
test -f "${ticket_state_skill_dir}/SKILL.md"
test -f "${ticket_state_skill_dir}/scripts/ticket_state.py"
```

project scopeや開発checkoutを使う場合は、`ticket_state_skill_dir`を実際のSkill directoryへ変更する。
Skill自体をまだインストールしていない場合は、リポジトリの`docs/installation.md`を先に参照する。

## 3. 設定と状態の親directoryをexportする

既存のXDG設定があれば維持し、未設定の場合だけ標準的な場所を使う。

```bash
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-${HOME}/.config}"
export XDG_STATE_HOME="${XDG_STATE_HOME:-${HOME}/.local/state}"

config_dir="${XDG_CONFIG_HOME}/agent-skills/ticket-state"
state_dir="${XDG_STATE_HOME}/agent-skills/ticket-state"

install -d -m 700 "${config_dir}"
install -d -m 700 "${state_dir}"
```

ticket-stateが末尾の`agent-skills/ticket-state`を追加するため、`XDG_CONFIG_HOME`や
`XDG_STATE_HOME`自体へその末尾を含めない。相対pathではなく絶対pathを推奨する。

## 4. config.tomlを作る

初回だけexampleをコピーする。既存configを上書きしないよう、先に存在を確認する。

```bash
config_file="${config_dir}/config.toml"

if [ ! -e "${config_file}" ]; then
  install -m 600 \
    "${ticket_state_skill_dir}/assets/config.example.toml" \
    "${config_file}"
fi

nano "${config_file}"
```

最初は利用するproviderだけを残し、write allowlistを追加しない構成が安全である。Backlogのread-only
疎通確認用の最小例は次のとおり。

```toml
schema_version = 1

[instances.backlog_test]
provider = "backlog"
base_url = "https://YOUR_SPACE.backlog.com"
api_key_env = "BACKLOG_API_KEY"

[profiles.backlog_test]
instance = "backlog_test"
project_id = 123456
project_key = "TEST"
read_scope = "project"
format = "markdown"
concurrency = "best_effort"
```

Redmineを使う場合はinstanceとprofileを次のようにする。subpathで運用している場合は`base_url`へ
含める。

```toml
schema_version = 1

[instances.redmine_test]
provider = "redmine"
base_url = "https://redmine.example.invalid/redmine"
api_key_env = "REDMINE_API_KEY"

[profiles.redmine_test]
instance = "redmine_test"
project_id = 17
read_scope = "project"
format = "textile"
concurrency = "best_effort"
```

主な設定値は次の意味を持つ。

| 項目 | 意味 |
|---|---|
| `instances.<name>` | 接続先に付ける任意の名前 |
| `provider` | `backlog`または`redmine` |
| `base_url` | HTTPSの接続先。Backlogはpathを付けない |
| `api_key_env` | API keyそのものではなく、後でexportする環境変数名 |
| `profiles.<name>` | Agentへ指定する利用profile名 |
| `project_id` | providerが返す数値project ID |
| `project_key` | Backlogだけに必要なproject key。Redmineでは指定しない |
| `format` | `markdown`、`backlog`、`textile`のいずれか。接続先の設定と一致させる |
| `concurrency` | 通常は`best_effort`。`strict`はserver-side conditional update未確認時に安全停止する |

`project_id`とBacklogの`project_key`は別の値である。管理者またはprovider APIで確認し、推測しない。
最初は`[profiles.<name>.write_allowlist]`を置かない。この状態でもreadでき、更新要求は
`PENDING_PERMISSION`となってremote mutationは0件になる。

## 5. Git repositoryごとのprofileをprivate設定へ紐づける

profile定義と同じconfig.tomlへ、端末内だけで使うrepository bindingを追加できる。`root`はcloneの
最上位directoryを絶対pathで指定する。

```toml
[repositories.monorepo_clone_a]
root = "/home/YOU/work/monorepo-profile-a"
profile = "profile_a"
workspace_id = "monorepo-profile-a"

[repositories.monorepo_clone_b]
root = "/home/YOU/work/monorepo-profile-b"
profile = "profile_b"
workspace_id = "monorepo-profile-b"
```

`profile_a`と`profile_b`は、同じconfig.tomlの`[profiles.profile_a]`と`[profiles.profile_b]`で定義する。
それぞれ異なるinstance、project、format、write allowlistを持てる。bindingが選ぶのはprofileと状態の
workspaceであり、ticket自体は選ばない。CLIではticketを引き続き明示する。Agentとの会話では、依頼中の
明示値、または今回の作業の正本として参照中のdesign doc等にある単一のtarget metadataから解決できる。

CLIはcurrent directoryから親へ辿り、最初に見つけた`.git`のdirectoryをrepository rootとする。
登録rootはsymlinkを解決した絶対pathで比較する。Git remote URLやrepository名は判定に使わないため、
同じmonorepoを2つのdirectoryへcloneしても、clone Aはprofile A、clone Bはprofile Bへ分離できる。

bindingはXDG配下のprivate configにだけ保存する。共有リポジトリの`AGENTS.md`、`.env`、tracked fileへ
追加しない。cloneを移動した場合は`root`を更新する。同じ実体を指すrootの重複、未知のprofile、相対path、
不正なworkspace IDはconfiguration errorになる。

clone内で解決結果を確認できる。このcommandはremote APIへ接続せず、API keyも必要としない。

```bash
cd /home/YOU/work/monorepo-profile-a
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" --json context
```

明示した`--profile`はbindingより優先する。どちらもない場合は既定profileを推測せず停止する。
`--workspace-id`を明示した場合もbindingのworkspace IDより優先する。

このpath-based bindingは、同じremoteの複数cloneを別profileとして扱う要件から設計したもので、local
corpusの観察結果を一般化したruleではない。解決優先順位やmatch条件の変更には、誤った接続先を選ばない
ための支持例・反例・境界例とhuman reviewを必要とする。

## 6. API keyを現在のshellへ入れる

次のBash例は入力文字を画面へ表示せず、shell historyへkey本体を含むコマンドを残さない。

```bash
read -rsp 'Backlog API key: ' BACKLOG_API_KEY
printf '\n'
export BACKLOG_API_KEY
```

Redmineの場合は変数名をconfigの`api_key_env`と一致させる。

```bash
read -rsp 'Redmine API key: ' REDMINE_API_KEY
printf '\n'
export REDMINE_API_KEY
```

値を表示せず、設定済みかだけを確認できる。

```bash
if [ -n "${BACKLOG_API_KEY:-}" ]; then
  echo 'BACKLOG_API_KEY is set'
else
  echo 'BACKLOG_API_KEY is not set'
fi
```

API keyを`.bashrc`、`.env`、config.toml、request JSON、CLI引数へ直接書かない。永続化が必要なら、
利用環境で承認されたsecret managerからshell環境変数へ読み込む。

## 7. Agent CLIを同じshellから起動する

export後に、普段使うAgent CLIを同じterminalから起動する。Codexの例:

```bash
codex
```

起動後は、最初にrepository bindingとreadだけを確認する。ticketはbindingから推測しないため、この例では
依頼で明示する。

```text
$ticket-stateを使い、current Git repositoryのcontextを確認してから、
ticket TEST-1をreadだけしてください。更新やproposal作成はしないでください。
```

Agentは子processとしてticket-state CLIを起動するため、XDGの保存先とAPI keyを継承する。
AgentへAPI keyの値をchatで貼り付ける必要はない。

## 8. Agentを介さずreadを確認する

問題の切り分けでは、同じshellからPython CLIを直接実行できる。global optionは`read`より前へ置く。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --json \
  read --ticket TEST-1
```

成功時は、選択したprofile、正規化済みticket identity、description、公開commentsなどをJSONで返す。
readはremoteを更新せず、proposalも作らない。出力にはticket本文が含まれるため、公開ログへ転送しない。
repository bindingを使わない場合は、従来どおり`read --profile backlog_test --ticket TEST-1`と明示する。

## 9. 状態directoryを確認する

更新案やdry-runを実行すると、既定では次の場所へ状態が保存される。

```text
${XDG_STATE_HOME}/agent-skills/ticket-state/<workspace-id>/
```

repository bindingがあれば、その`workspace_id`を使う。bindingがなくworkspace IDも省略した場合は、
実行時のcurrent working directoryから`workspace-...`というIDを生成する。

保存済みの未反映proposalは次のように確認する。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --workspace-id backlog-test \
  pending
```

状態directoryにはSQLite DB、remoteから取得した本文、diff、予定payload、receipt、template artifactが
含まれる。API keyは保存しないが、ticketの非公開情報を含み得るため、公開・commit・安易な削除をしない。

既定値を使わない場合は、global optionで明示できる。

```bash
python3 "${ticket_state_skill_dir}/scripts/ticket_state.py" \
  --config /private/ticket-state/config.toml \
  --work-dir /private/ticket-state/state \
  --workspace-id backlog-test \
  pending
```

`--work-dir`はworkspace IDを追加する前の親directoryを指定する。

## 10. 最初のwrite allowlist

readとdry-runを確認してから、書き込みを許可するticketだけをconfigへ追加する。

```toml
[profiles.backlog_test.write_allowlist]
"TEST-1" = ["comment:append"]
```

descriptionとsnapshotのcombined updateも許可する場合だけ、権限を追加する。

```toml
[profiles.backlog_test.write_allowlist]
"TEST-1" = ["description:write", "comment:append"]
```

project全体やwildcardは指定できない。allowlistを変更しても、過去のdry-runを自動適用しない。
実書き込み前に最新remote、diff、対象ticket、必要permissionを再確認する。

## 11. よくあるエラー

| 表示 | 確認すること |
|---|---|
| `cannot load config` | `XDG_CONFIG_HOME`をexportしたshellから起動したか、config pathとpermissionが正しいか |
| `API key environment variable ... is not set` | `api_key_env`の名前とexportした変数名が一致するか、Agentをexport後に再起動したか |
| `unknown profile` | `[profiles.<name>]`と依頼・CLIの`--profile`が一致するか |
| repository bindingなし | current cloneの絶対rootが`[repositories.<name>]`と一致するか |
| identityやproject不一致 | 数値`project_id`、Backlogの`project_key`、ticket keyを推測せず確認したか |
| format不一致 | provider側のtext formatting設定とconfigの`format`が一致するか |
| `PENDING_PERMISSION` | write allowlistがないread-only状態では正常。remoteは更新されていない |
| work directory拒否 | symlinkではないprivate pathか、Git repository内なら確実にignore済みか |

作業終了時は、現在のshellからAPI keyを外せる。

```bash
unset BACKLOG_API_KEY
unset REDMINE_API_KEY
```

状態directoryは監査と再開の記録なので、API keyをunsetする流れで一緒に削除しない。

セットアップ後の通常の依頼方法は[Agentとの使い方](using-with-agent.md)を参照する。CLI commandの引数や
直接実行による切り分けが必要な場合は、[コマンドリファレンス](command-reference.md)を参照する。
