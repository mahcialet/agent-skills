# インストール

このリポジトリの各Skillは、GitHubから取得した内容を固定して使う方法でも、ローカルの
編集内容を即座に反映させながら開発する方法でもインストールできる。

## 利用できるSkill

| Skill | 主な用途 | 既定動作 |
|---|---|---|
| `reader-first-editor` | 日本語・英語の文章を、一度で理解しやすく、内容を変えずに整える | 原文やファイルを変更しない文章レビュー |
| `adversarial-pr-review` | 差分外の証拠とA0〜A4によるPR・diff review | GitHub上の状態やファイルを変更しないコードレビュー |

以下の例では、最初に `skill_name` を設定する。コマンド例では
`reader-first-editor` を使うが、`adversarial-pr-review` も指定できる。

| 目的 | 推奨方法 | 特徴 |
|---|---|---|
| 通常利用 | `gh skill install` | GitHubから取得し、更新元を追跡できる |
| 現在の作業ツリーを試す | `install-local.sh`（既定はコピー） | インストール後の内容が固定される |
| Skillを開発する | `install-local.sh --link` | 作業ツリーの変更が即座に反映される |
| `gh skill` を使えない環境 | 手動コピー | 標準配置先へ自分でコピーする |

コマンドは、特記がない限りこのリポジトリのルートで実行する。

<a id="scopeと配置先"></a>

## scope（適用範囲）と配置先

`--scope` はSkillを利用できる範囲を指定する。

| scope | 配置先 | 利用範囲 |
|---|---|---|
| `user` | `$HOME/.agents/skills/<skill-name>` | そのユーザーが起動するすべてのプロジェクト |
| `project` | `<現在のリポジトリ>/.agents/skills/<skill-name>` | そのプロジェクトと配下の作業ディレクトリ |

CodexとGitHub Copilotは、どちらも上記の `.agents/skills` を読める。そのため、
ローカル補助スクリプトの `--agent codex` と `--agent github-copilot` は同じ標準配置先を
使用する。`--agent` では対象ホストを明示する。これにより、対象ホストの誤指定を
検出でき、実行結果から対象を確認できる。

個人の全プロジェクトで使うなら `user`、チームで共有するプロジェクトだけに限定するなら
`project` を選ぶ。`project` scopeの `.agents/skills` は、必要に応じて対象プロジェクトの
Gitで管理できる。

## GitHub CLI（public preview）

GitHub CLI 2.97.0で、`skills/*/SKILL.md` の検出、CodexとGitHub Copilotへの
インストール、タグまたはcommit SHAによる固定を確認している。通常利用ではこの方法を
推奨する。

```bash
skill_name=reader-first-editor # adversarial-pr-reviewも指定可能

# Codexで、すべてのprojectから使えるようにする
gh skill install mahcialet/agent-skills "${skill_name}" \
  --agent codex --scope user

# GitHub Copilotで、すべてのprojectから使えるようにする
gh skill install mahcialet/agent-skills "${skill_name}" \
  --agent github-copilot --scope user

# Codexで、現在のprojectだけから使えるようにする
gh skill install mahcialet/agent-skills "${skill_name}" \
  --agent codex --scope project

# 検証済みの内容を再現できるよう、取得元をcommit SHAへ固定する
commit_sha=REPLACE_WITH_COMMIT_SHA
gh skill install mahcialet/agent-skills "${skill_name}" \
  --agent codex --scope user --pin "${commit_sha}"

# GitHubではなく、現在のローカル作業ツリーからproject scopeへコピーする
gh skill install . "${skill_name}" --from-local \
  --agent codex --scope project
```

`adversarial-pr-review` をuser scopeへ入れる具体例:

```bash
gh skill install mahcialet/agent-skills adversarial-pr-review \
  --agent codex --scope user
gh skill install mahcialet/agent-skills adversarial-pr-review \
  --agent github-copilot --scope user
```

`gh skill` はpublic previewであり、オプションや配置が変更される可能性がある。
使用する内容を固定する必要がある環境では、`--pin` を指定する。例にある
`REPLACE_WITH_COMMIT_SHA` は、内容を確認済みのcommit SHAへ置き換える。固定しない場合、
インストーラーはリポジトリのreleaseまたはdefault branchを解決するため、後日
再インストールすると内容が変わる可能性がある。

`--from-local` は作業ツリーの内容をコピーする。コピー後に元ファイルを編集しても、
インストール済みのコピーへは自動反映されない。元ファイルの変更を継続的に反映する
開発では、後述の `--link` を使用する。

## ローカル補助スクリプト

`scripts/install-local.sh` は、このリポジトリ内のSkillを標準配置先へコピーするか、
シンボリックリンクで配置する。GitHubからのdownloadは行わない。コピー時には、インストール元を
識別できるよう、配置先の `SKILL.md` の説明へ短縮Git commit ID、commitのtreeとの違い、または
commit IDを取得できない理由を追加する。スクリプトの実行にはPython 3.10以降が必要である。

```text
Usage: ./scripts/install-local.sh <skill-name> \
  [--scope user|project] \
  [--agent codex|github-copilot] \
  [--link] [--force]
```

| option | 既定値 | 意味 |
|---|---|---|
| `<skill-name>` | なし | `reader-first-editor` または `adversarial-pr-review` |
| `--scope` | `project` | `user` scopeまたは`project` scopeを選ぶ |
| `--agent` | `codex` | 対象ホストを明示する |
| `--link` | 無効 | コピーではなくシンボリックリンクを作る |
| `--force` | 無効 | 既存先を `.agents/backups` へ移してから置き換える |

<a id="copyでインストールする"></a>

### コピーしてインストールする

```bash
# ~/.agents/skills/reader-first-editor へコピーする
./scripts/install-local.sh reader-first-editor --scope user --agent codex

# このリポジトリの .agents/skills/reader-first-editor へコピーする
./scripts/install-local.sh reader-first-editor \
  --scope project --agent github-copilot
```

コピーすると、インストール時点の内容が独立したディレクトリに保存される。元の
`skills/reader-first-editor` を後から編集しても、インストール済みのコピーは変わらない。
普段使いや、検証済みの内容を意図せず変えたくない場合に適している。

コピーでは、リポジトリ内の元ファイルを変更せず、配置先の `SKILL.md` にある
`description` の末尾へ次の情報を追加する。

| インストール元の状態 | 配置先の説明へ追加する内容 |
|---|---|
| コピー内容がcommitのtreeと一致する | `Install source: Git commit <short-commit-id>.` |
| コピー内容がcommitのtreeと異なる | `Install context: Git HEAD <short-commit-id>; copied Skill differs from the committed tree.` |
| まだコミットを作成していないGit作業ツリー | `Install source: unborn Git worktree; copied content has no commit ID.` |
| Gitリポジトリではない | `Install source: non-Git directory; no commit ID is available.` |
| Gitコマンドを利用できない | `Install source: Git unavailable; no commit ID is available.` |

commitのtreeと異なる内容には、対象Skill内のステージ済みまたは未ステージの変更、未追跡ファイル、
Gitの無視対象になっているファイルやディレクトリが含まれる。Git LFSや改行コードの変換などにより、
Git上では変更なしと表示される作業ツリーでも、実際のファイルがcommit内のbytesと異なればこちらに
該当する。スクリプトは実際にコピーしたsnapshotを、commitのpath、file type、bytes、実行権限、
シンボリックリンクの参照先と比較する。差分そのものは表示しない。対象Skillの外にある変更だけでは、
コピー内容がcommitのtreeと異なるとは表示しない。

説明に記録するcommit IDは、読みやすさのため `git rev-parse --short=12` が返す短縮形にする。
通常は先頭12文字で、同じ接頭辞を持つobjectがある場合は、一意に識別できる長さまでGitが延長する。
コピー内容の比較には完全なIDを使うため、表示を短くしても判定対象は変わらない。コピー内容が
異なる場合のIDは、コピー内容そのものを固定する値ではなく、その作業ツリーの基点となるHEADで
ある。同じHEADから異なる内容をコピーすることもあるため、コピー内容のハッシュ、署名、
リリース版番号とはみなさない。
Gitコマンドを利用できない場合は、上表の理由を記録してコピーを続ける。一方、リポジトリに
Gitの管理情報があるのにHEADや対象Skillの状態を正常に調べられない場合は、既存の配置先を
動かす前に処理を中止する。

`adversarial-pr-review` をコピーする場合も同じである。

```bash
./scripts/install-local.sh adversarial-pr-review --scope user --agent codex
./scripts/install-local.sh adversarial-pr-review \
  --scope project --agent github-copilot
```

### `--link` で開発用にインストールする

```bash
./scripts/install-local.sh reader-first-editor \
  --scope user --agent codex --link
```

`--link` はファイルを複製せず、配置先にシンボリックリンクを作る。上の例での配置先と
元ディレクトリの関係は、次のとおりである。

```text
$HOME/.agents/skills/reader-first-editor
  -> <このリポジトリ>/skills/reader-first-editor
```

このリポジトリのSkillを編集すると、シンボリックリンク経由でSkillを読むホストにも変更が即座に
反映される。そのため、再インストールせずに動作を確認できる。Skill開発に使う場合は、
次の点に注意する。

- リポジトリを移動・rename・削除するとリンクが切れる。
- ブランチ切替えや未commitの編集も、そのまま利用内容へ反映される。
- 検証済み内容を固定したい運用環境にはコピーまたはSHA pinを使う。
- Codexでは開発用途に利用できる。Copilotでシンボリックリンクを使う場合は、利用するOSと
  CLI versionで検出を確認する。

リンク先は作成後も内容が変わるため、`--link` では `SKILL.md` の説明へcommit IDを追加しない。
スクリプトの実行結果には、リンクであることと作成時点のcommit ID、基点となるHEAD、または
commit IDを取得できない理由を表示する。
利用中の内容を後から確認するときは、リンク元のリポジトリで改めてHEADと作業ツリーを確認する。

### 既存インストールを置き換える

配置先がすでに存在する場合、スクリプトは何も上書きせず終了する。意図的に
置き換える場合だけ `--force` を付ける。

```bash
./scripts/install-local.sh reader-first-editor \
  --scope user --agent codex --force

# 既存のコピーを開発用リンクへ置き換える
./scripts/install-local.sh reader-first-editor \
  --scope user --agent codex --link --force
```

`--force` を付けても既存の配置先はすぐに削除しない。既存のコピーまたはシンボリックリンクを
Skillの探索先から外し、次のような時刻付きバックアップへ移動してから新しい配置先を作る。

```text
user scope:
$HOME/.agents/backups/reader-first-editor.backup.20260830153000

project scope:
<このリポジトリ>/.agents/backups/reader-first-editor.backup.20260830153000
```

[OpenAI Docs](https://learn.chatgpt.com/docs/build-skills)に記載されているとおり、Codexは
`.agents/skills` を探索し、同じ `name` のSkillも一つに統合しない。この直下にバックアップを
置くと、バックアップ内の `SKILL.md` も別のSkill候補として検出されることがある。そのため、
現在使うSkillだけを `.agents/skills` に置き、バックアップは探索範囲外の `.agents/backups` に
分ける。同じ時刻の名前がすでにある場合は、連番を付けて上書きを避ける。

コピーのバックアップには置換前のファイルが残る。一方、シンボリックリンクのバックアップに
残るのはリンク自体であり、リンク先の内容を固定した複製ではない。リンク先を編集・移動・
削除すると、バックアップから参照できる内容も変わるか、リンクが切れる。

旧版のスクリプトが `.agents/skills/<name>.backup.<timestamp>` に作成したバックアップは、
同じSkillを次にインストールし直すとき、`.agents/backups` へ自動的に移動する。現在使っている
Skillがあり `--force` を付けていない場合は、インストーラーが先に終了するため移動しない。
現在のSkillを置き換えずに旧バックアップだけを候補から外す場合は、対象のバックアップを
`.agents/skills` から同じscopeの `.agents/backups` へ手動で移動する。

以前のコピーへ戻す場合は、現在の配置先を別の場所へ退避してから、選んだバックアップを元の
配置先へ戻す。復旧先はuser scopeなら `$HOME/.agents/skills/<name>`、project scopeなら
`<このリポジトリ>/.agents/skills/<name>` である。シンボリックリンクのバックアップを戻す場合は、
リンク先がまだ存在し、意図した内容を指していることを先に確認する。新しい配置先の作成に失敗し、
元の配置先を安全に戻せる場合は、スクリプトが自動的に復旧する。復旧できなかった場合も、実行結果に
表示されたバックアップの場所から手動で戻せる。不要になったバックアップは、内容を確認してから
手動で削除する。

## 手動コピー

`gh skill` や補助スクリプトを使わない場合は、Skillディレクトリ全体を標準配置先へ
コピーする。`SKILL.md` だけではなく、`references/`、`assets/`、`examples/`、
`agents/`、`scripts/` なども必要なため、ディレクトリ単位でコピーする。
手動コピーではcommit IDを説明へ自動追加しないため、必要なら取得元のcommit IDを別途記録する。

CodexとCopilot CLIが共通で読むuser scopeへ配置する例:

```bash
mkdir -p "$HOME/.agents/skills"
cp -R skills/adversarial-pr-review "$HOME/.agents/skills/adversarial-pr-review"
```

project scopeへ配置する例:

```bash
mkdir -p .agents/skills
cp -R skills/adversarial-pr-review .agents/skills/adversarial-pr-review
```

Copilot固有のuser scopeである `~/.copilot/skills` も利用できるが、Codexと共有
したい場合は `$HOME/.agents/skills` を使う。

## インストールを確認する

配置後、新しいセッションを開始する。すでにCopilot CLIを起動している場合は、
`/skills reload` で再読込みできる。

`install-local.sh` でコピーした場合は、Skillの詳細表示または配置先の `SKILL.md` を開き、
`description` の末尾にある `Install source:` または `Install context:` を確認する。`--link` では
この情報を追加しないため、リンク元のリポジトリでHEADと作業ツリーを確認する。

- Codex: Skill一覧で対象名を確認し、`$reader-first-editor ...` または
  `$adversarial-pr-review ...` で明示起動する。
- Copilot CLI: `/skills list`、`/skills info reader-first-editor`、または
  `/skills info adversarial-pr-review` で確認し、
  `/reader-first-editor ...` または `/adversarial-pr-review ...` で明示起動する。

最初は破棄しても問題のない、本番データではない試験用の入力を `review` させ、原文や
ファイルを変更しない既定動作を確認する。

```text
$reader-first-editor 次の文をreviewしてください。書き換えは不要です: ...
$adversarial-pr-review disposable repoのstaged changesをlevel=A1、depth=focusedでreviewしてください。
```

各Skillの固有契約（mode、変更範囲、安全上の制約、出力）は、
[`reader-first-editor` のREADME](../skills/reader-first-editor/README.md)と
[`adversarial-pr-review` のREADME](../skills/adversarial-pr-review/README.md)に記載する。
`reader-first-editor` の改稿にはmodeの明示が必要である。`adversarial-pr-review` のreviewと
gateは、どちらも対象を変更せず、結果の報告だけを行う。

## 更新

更新方法はインストール方式によって異なる。

- `gh skill install` で配置した場合: `gh skill update` を使い、適用前後の差分と
  更新元を確認する。
- コピーした場合: 新しいcommitをcheckoutし、既存先をバックアップしたうえで再コピーする。
- `--link` の場合: checkout中の作業ツリーがそのまま反映される。ブランチ切替え前に
  差分を確認する。

運用環境では単なる「最新」ではなく、検証済みSHAを記録する。

## 明示起動

- Codex: `$reader-first-editor ...` または `$adversarial-pr-review ...`
- Copilot CLI: `/reader-first-editor ...` または `/adversarial-pr-review ...`

どちらも意図せず時間や計算資源を使うreviewや編集を避けるため、明示起動を標準とする。
Codexでは各Skillの `agents/openai.yaml` に `allow_implicit_invocation: false` を設定している。
