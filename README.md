# Agent Skills

Codex、GitHub Copilot、およびオープンなAgent Skills形式を実装するホスト向けの
portableなSkillを管理するモノレポです。外部リンク集ではなく、掲載するSkill本体の
source of truthです。

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

各Skillの適用範囲、安全境界、第三者attributionは、それぞれのREADMEとNOTICEに記載して
います。

## インストール

GitHub CLI 2.97以降は、このリポジトリの `skills/*/SKILL.md` を検出できます。

```bash
skill_name=reader-first-editor # adversarial-pr-reviewも指定可能
gh skill install mahcialet/agent-skills "${skill_name}" --agent codex --scope user
gh skill install mahcialet/agent-skills "${skill_name}" --agent github-copilot --scope user
```

`gh skill` はpublic previewです。手動配置とcommit SHA固定は
[インストール](docs/installation.md)に記載しています。

## リポジトリガイド

- [アーキテクチャ](docs/architecture.md)
- [Skillの追加](docs/adding-a-skill.md)
- [互換性](docs/compatibility.md)
- [インストール](docs/installation.md)
- [Licensing](docs/licensing.md)
- [リリース方針](docs/release-policy.md)
- [コントリビューション](CONTRIBUTING.md)

## 検証

PRを作る前に `./scripts/validate-skills.sh` を実行してください。portableな
frontmatter、内部参照、NOTICE、fixture、カタログの整合を確認します。利用可能な
場合、CIは `gh skill publish --dry-run` も実行します。

## License

Original repository content is available under the [MIT License](LICENSE).
Third-party attributions and material with separate terms are listed in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
