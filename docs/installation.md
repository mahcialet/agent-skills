# インストール

## GitHub CLI（public preview）

GitHub CLI 2.97.0で、`skills/*/SKILL.md` の検出、CodexとGitHub Copilotへの
インストール、タグまたはcommit SHAへのpinを確認している。

```bash
# Codexのuser scope
gh skill install mahcialet/agent-skills reader-first-editor \
  --agent codex --scope user

# GitHub Copilotのuser scope
gh skill install mahcialet/agent-skills reader-first-editor \
  --agent github-copilot --scope user

# 再現可能なcommit SHA固定
gh skill install mahcialet/agent-skills reader-first-editor \
  --agent codex --scope user --pin <COMMIT_SHA>

# ローカル作業ツリーから検証用にコピー
gh skill install . reader-first-editor --from-local \
  --agent codex --scope project
```

`gh skill` はpublic previewであり、オプションや配置が変更される可能性がある。
固定が必要な環境ではcommit SHAを指定し、更新前にreviewする。

## 手動コピー

CodexとCopilot CLIが共通で読むuser scope:

```bash
cp -R skills/reader-first-editor "$HOME/.agents/skills/reader-first-editor"
```

project scopeでは対象リポジトリの
`.agents/skills/reader-first-editor` へコピーする。Copilot固有のuser scope
`~/.copilot/skills` も利用できる。

## ローカル補助スクリプト

```bash
./scripts/install-local.sh reader-first-editor --scope user --agent codex
./scripts/install-local.sh reader-first-editor --scope project --agent github-copilot
./scripts/install-local.sh reader-first-editor --scope user --agent codex --link
```

既存先は自動上書きしない。`--force` を指定した場合も、既存ディレクトリを時刻
付きbackupへ移してから配置する。symlinkはCodex開発時に利用できる。Copilotでの
symlinkは利用環境で検証してから採用する。

## 更新

`gh skill update` を使う場合も、差分と新しい参照先を確認する。手動配置は新しい
commitをcheckoutした後に再コピーする。運用環境では「最新」ではなく、検証済み
SHAを記録する。

## 明示起動

- Codex: `$reader-first-editor ...`
- Copilot CLI: `/reader-first-editor ...`

既定は非破壊の `review`。改稿する場合は `revise-safe` などのモードを明示する。
