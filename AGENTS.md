---
status: active
owner: maintainers
last_verified: 2026-09-11
---

# リポジトリ指示

[English](AGENTS.en.md) は同じ方針の翻訳であり、別の挙動定義ではない。
設計・検証・作業計画の入口は [文書案内](docs/index.md)、
[アーキテクチャ](docs/architecture.md)、[品質](docs/QUALITY.md)、[Plans](docs/PLANS.md)。

## 適用範囲

この指示はリポジトリ全体に適用する。

## Skill設計

- すべての対応ホストが、`skills/<name>/SKILL.md` にある同じ挙動定義を使う。
- Codex版とCopilot版を手書きで複製しない。
- provider固有のmetadataを共通instructionsから分離する。
- Skillが実行時に読むファイルを、各Skillディレクトリ内に収める。
- ユーザーが明示的に編集を求めない限り、編集Skillが原文やファイルを変更しないようにする。

## 文書

- リポジトリ内の説明文書は日本語を基本とする。
- ホストがSkillを検出するためのfrontmatter、CLI・schemaの識別子、license原文、保持が
  必要な引用は、必要に応じて英語のまま記載する。
- コード識別子やschema keyを、日本語文書方針だけを理由に翻訳しない。
- planned、experimental、implemented、verifiedを区別し、未実装の機能を利用可能と
  表現しない。
- 今回新設・実質更新する永続説明文書とExecPlanは、日本語原本 `.md` と英語訳 `.en.md` を揃える。
  `SKILL.md` はホスト・言語別に複製しない。翻訳hashの一致を意味の一致とみなさない。

## 検証と作業計画

- 正規入口は `python -m tools.repoctl verify`。準備・証拠・制約は品質文書を読む。
- `check` は静的検証、`test --list` はsuite一覧、`test` は実行。通常検証は実モデル・実host・本番APIを起動しない。
- `docs-check`、`generated-check`、`plans list/check` は読み取り専用。生成の変更は明示 `generate` のみ。
- 承認された範囲と残件をExecPlanに記録する。draft・paused・human Planを自動実行しない。
- 未mergeのPlanをcompletedにしない。merge、実モデル・実host起動は個別の許可範囲を守る。

## 変更

- 第三者由来要素のattribution（出典・著作者表示など）とlicense noticeを保存する。
- 挙動を変更するときはexamplesとeval fixtureを更新する。
- Skillの挙動を変えるルール（behavior-changing rule）には、支持例、反例、境界例、
  既存evalで回帰がないことの確認、出典と来歴（provenance）の確認、人間による明示的な
  reviewを要求する。
- local corpusの観察結果を、人間が審査しないままcore ruleへ昇格しない。
- ルートカタログと `skills/` を同期する。
- commit前に `./scripts/validate-skills.sh` を実行する。
- commitを目的別に分け、force pushしない。
