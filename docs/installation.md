# インストール

このリポジトリの各Skillは、GitHubから取得して固定的に使う方法と、ローカルの
編集内容を即座に反映させながら開発する方法のどちらでもインストールできる。

## 利用できるSkill

| Skill | 主な用途 | 既定動作 |
|---|---|---|
| `reader-first-editor` | 日本語・英語文章の初読理解と意味保存 | read-onlyの文章review |
| `adversarial-pr-review` | 差分外の証拠とA0〜A4によるPR・diff review | read-onlyのcode review |

以下の一般例では、最初に `skill_name` を設定する。例では
`reader-first-editor` を使うが、`adversarial-pr-review` も指定できる。

| 目的 | 推奨方法 | 特徴 |
|---|---|---|
| 通常利用 | `gh skill install` | GitHubから取得し、更新元を追跡できる |
| 現在の作業ツリーを試す | `install-local.sh`（既定のcopy） | インストール後の内容が固定される |
| Skillを開発する | `install-local.sh --link` | 作業ツリーの変更が即座に反映される |
| `gh skill` を使えない環境 | 手動copy | 標準配置先へ自分でコピーする |

コマンドは、特記がない限りこのリポジトリのルートで実行する。

## scopeと配置先

`--scope` はSkillを利用できる範囲を指定する。

| scope | 配置先 | 利用範囲 |
|---|---|---|
| `user` | `$HOME/.agents/skills/<skill-name>` | そのユーザーが起動するすべてのproject |
| `project` | `<現在のリポジトリ>/.agents/skills/<skill-name>` | そのprojectと配下の作業ディレクトリ |

CodexとGitHub Copilotは、どちらも上記の `.agents/skills` を読める。そのため、
ローカル補助スクリプトの `--agent codex` と `--agent github-copilot` は同じ標準配置先を
使用する。`--agent` は対象ホストを明示して誤指定を検出し、実行結果を分かりやすく
するための指定である。

個人の全projectで使うなら `user`、チームで共有するprojectだけに限定するなら
`project` を選ぶ。project scopeの `.agents/skills` は、必要に応じて対象projectの
Gitで管理できる。

## GitHub CLI（public preview）

GitHub CLI 2.97.0で、`skills/*/SKILL.md` の検出、CodexとGitHub Copilotへの
インストール、タグまたはcommit SHAへのpinを確認している。通常利用ではこの方法を
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
固定が必要な環境では `--pin` を指定する。例にある `REPLACE_WITH_COMMIT_SHA` は、
使用する内容を確認済みのcommit SHAへ置き換える。pinしない場合、installerはrepositoryの
releaseまたはdefault branchを解決するため、後日の再インストール結果が変わる
可能性がある。

`--from-local` は作業ツリーの内容をコピーする。元ファイルを編集しても、すでに
インストールしたcopyへは自動反映されない。継続的な開発には、後述の `--link` を
使用する。

## ローカル補助スクリプト

`scripts/install-local.sh` は、このリポジトリ内のSkillを標準配置先へcopyまたは
symlinkで配置する。GitHubからのdownloadは行わない。

```text
Usage: ./scripts/install-local.sh <skill-name> \
  [--scope user|project] \
  [--agent codex|github-copilot] \
  [--link] [--force]
```

| option | 既定値 | 意味 |
|---|---|---|
| `<skill-name>` | なし | `reader-first-editor` または `adversarial-pr-review` |
| `--scope` | `project` | user scopeまたはproject scopeを選ぶ |
| `--agent` | `codex` | 対象ホストを明示する |
| `--link` | 無効 | copyではなくsymlinkを作る |
| `--force` | 無効 | 既存先をbackupへ移してから置き換える |

### copyでインストールする

```bash
# ~/.agents/skills/reader-first-editor へcopyする
./scripts/install-local.sh reader-first-editor --scope user --agent codex

# このリポジトリの .agents/skills/reader-first-editor へcopyする
./scripts/install-local.sh reader-first-editor \
  --scope project --agent github-copilot
```

copyは、インストール時点の内容を独立したディレクトリとして保存する。元の
`skills/reader-first-editor` を後から編集しても、インストール済みcopyは変わらない。
普段使いや、検証済み内容を意図せず変えたくない場合に適している。

`adversarial-pr-review` をcopyする場合も同じである。

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

`--link` はファイルを複製せず、配置先にsymlinkを作る。上の例では、概念的に次の
関係になる。

```text
$HOME/.agents/skills/reader-first-editor
  -> <このリポジトリ>/skills/reader-first-editor
```

このリポジトリのSkillを編集すると、リンク先を読むホストにも変更が即座に反映
されるため、再インストールせず動作確認できる。Skill開発には便利だが、次の点に
注意する。

- リポジトリを移動・rename・削除するとリンクが切れる。
- branch切替えや未commitの編集も、そのまま利用内容へ反映される。
- 検証済み内容を固定したい運用環境にはcopyまたはSHA pinを使う。
- Codexでは開発用途に利用できる。Copilotでsymlinkを使う場合は、利用するOSと
  CLI versionで検出を確認する。

### 既存インストールを置き換える

配置先がすでに存在する場合、スクリプトは何も上書きせず終了する。意図的に
置き換える場合だけ `--force` を付ける。

```bash
./scripts/install-local.sh reader-first-editor \
  --scope user --agent codex --force

# 既存のcopyを開発用linkへ置き換える
./scripts/install-local.sh reader-first-editor \
  --scope user --agent codex --link --force
```

`--force` でも既存内容は削除しない。たとえば次のような時刻付きbackupへ移動して
から、新しいcopyまたはlinkを作る。

```text
reader-first-editor.backup.20260830153000
```

不要になったbackupは、内容を確認してから手動で削除する。

## 手動コピー

`gh skill` や補助スクリプトを使わない場合は、Skillディレクトリ全体を標準配置先へ
コピーする。`SKILL.md` だけではなく、`references/`、`assets/`、`examples/`、
`agents/`、`scripts/` なども必要なため、ディレクトリ単位でコピーする。

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

配置後、新しいセッションを開始する。すでにCopilot CLIを起動している場合は
`/skills reload` で再読込みできる。

- Codex: Skill一覧で対象名を確認し、`$reader-first-editor ...` または
  `$adversarial-pr-review ...` で明示起動する。
- Copilot CLI: `/skills list`、`/skills info reader-first-editor`、または
  `/skills info adversarial-pr-review` で確認し、
  `/reader-first-editor ...` または `/adversarial-pr-review ...` で明示起動する。

最初は破棄可能な入力を `review` させ、非破壊の既定動作を確認する。

```text
$reader-first-editor 次の文をreviewしてください。書き換えは不要です: ...
$adversarial-pr-review disposable repoのstaged changesをlevel=A1、depth=focusedでreviewしてください。
```

各Skillの固有契約はSkill READMEに記載する。`reader-first-editor` の改稿にはmodeの明示が
必要で、`adversarial-pr-review` のreviewとgateはいずれもread-only／report-onlyである。

## 更新

更新方法はインストール方式によって異なる。

- `gh skill install` で配置した場合: `gh skill update` を使い、適用前後の差分と
  更新元を確認する。
- copyした場合: 新しいcommitをcheckoutし、既存先をbackupしたうえで再コピーする。
- `--link` の場合: checkout中の作業ツリーがそのまま反映される。branch切替え前に
  差分を確認する。

運用環境では単なる「最新」ではなく、検証済みSHAを記録する。

## 明示起動

- Codex: `$reader-first-editor ...` または `$adversarial-pr-review ...`
- Copilot CLI: `/reader-first-editor ...` または `/adversarial-pr-review ...`

どちらも意図しない高コストreviewや編集を避けるため、明示起動を標準とする。Codexでは
各Skillの `agents/openai.yaml` に `allow_implicit_invocation: false` を設定している。
