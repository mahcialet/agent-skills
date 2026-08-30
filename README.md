# Agent Skills

Codex、GitHub Copilot、およびオープンなAgent Skills形式に対応するホストで使うSkillを、
一つのリポジトリで管理しています。外部リンクだけを集めた一覧ではありません。掲載する
各Skillについて、実行に必要な本体と関連ファイルを収録しています。

## Skills

<!-- BEGIN GENERATED SKILL CATALOG -->
### Writing and Review

| Skill | Codex | Copilot | Languages | Stability | Description | License |
|---|:---:|:---:|---|---|---|---|
| [reader-first-editor](skills/reader-first-editor/README.md) | ✓ | ✓ | ja, en | experimental | 読み返しや誤解、リポジトリ内の実態との乖離を診断し、意味を損なわず文章を整える | [MIT + notices](skills/reader-first-editor/NOTICE.md) |

### Code Review

| Skill | Codex | Copilot | Languages | Stability | Description | License |
|---|:---:|:---:|---|---|---|---|
| [adversarial-pr-review](skills/adversarial-pr-review/README.md) | ✓ | ✓ | ja, en | experimental | 差分外の証拠探索とA0〜A4の敵対性レベルでPR・diffをレビューする | [MIT + notices](skills/adversarial-pr-review/NOTICE.md) |

<!-- END GENERATED SKILL CATALOG -->

各Skillを使える場面、利用時に守る制約、第三者由来要素の出典・著作者表示とライセンス通知は、
それぞれのREADMEとNOTICEに記載しています。

## Behavior Profiles（実験）

[`behavior-profiles/`](behavior-profiles/README.md) には、既存能力の使い方を定める任意の
conduct layerをSkillとは分離して収録しています。ProfileはSkillやtool-level enforcementでは
ありません。PoCでは `AGENTS.md` 用managed blockをdefault read-only installerで生成します。
構造検証の成功と実Agentのbehavior evidenceも別に扱います。設計、install、uninstall、
`independent-adversarial-verification` 固有の3つのreview modeは
[試験運用ガイド](docs/behavior-profiles.md)を参照してください。

現在のartifactは `implemented` かつ `structurally validated` です。2026-08-31にCodex CLI
0.151.0とGitHub Copilot CLI 1.0.82の正式S01〜S10を`gpt-5.4`で観測しました。これは
[記録した条件でのevidence](behavior-profiles/evidence/README.md)に限る`observed`であり、別の
host、version、modelやproductionでの挙動を`verified`とするものではありません。

## インストール

GitHub CLI 2.97以降は、このリポジトリの `skills/*/SKILL.md` を検出できます。

```bash
skill_name=reader-first-editor # adversarial-pr-reviewも指定可能
gh skill install mahcialet/agent-skills "${skill_name}" --agent codex --scope user
gh skill install mahcialet/agent-skills "${skill_name}" --agent github-copilot --scope user
```

`gh skill` はpublic previewです。手動配置とcommit SHAによる固定は
[インストール](docs/installation.md)に記載しています。

## リポジトリガイド

- [アーキテクチャ](docs/architecture.md)
- [Skillの追加](docs/adding-a-skill.md)
- [互換性](docs/compatibility.md)
- [インストール](docs/installation.md)
- [Behavior Profilesの試験運用](docs/behavior-profiles.md)
- [Licensing](docs/licensing.md)
- [リリース方針](docs/release-policy.md)
- [コントリビューション](CONTRIBUTING.md)

## 検証

PRを作る前に `./scripts/validate-skills.sh` を実行してください。Skillに加えて、Behavior
Profile専用のfrontmatter、required section、参照先、NOTICE、pressure test、catalogも
検査します。この成功が示すのはpackageの構造整合性だけで、実Agentのbehaviorではありません。
利用可能な場合、CIは `gh skill publish --dry-run` も実行します。

## License

Original repository content is available under the [MIT License](LICENSE).
Third-party attributions and material with separate terms are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
