# リポジトリ指示

## 適用範囲

この指示はリポジトリ全体に適用する。

## Skill設計

- `skills/<name>/SKILL.md` を、すべての対応ホストが共有する唯一の正本にする。
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
