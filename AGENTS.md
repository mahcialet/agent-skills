# リポジトリ指示

## 適用範囲

この指示はリポジトリ全体に適用する。

## Skill設計

- `skills/<name>/SKILL.md` をportableなsource of truthにする。
- Codex版とCopilot版を手書きで複製しない。
- provider固有metadataを共通instructionsから分離する。
- 実行時参照を各Skillディレクトリ内に収める。
- ユーザーが明示的に編集を求めない限り、編集Skillを非破壊動作にする。

## 文書

- リポジトリ内の説明文書は日本語を基本とする。
- host discovery用のfrontmatter、CLI・schemaの識別子、license原文、保持が必要な引用は、
  必要に応じて英語のまま記載する。
- コード識別子やschema keyを、日本語文書方針だけを理由に翻訳しない。
- planned、experimental、implemented、verifiedを区別し、未実装の機能を利用可能と
  表現しない。

## 変更

- 第三者attributionとlicense noticeを保存する。
- 挙動変更時はexamplesとeval fixtureを更新する。
- behavior-changing ruleには、支持例、反例、境界例、既存evalの回帰確認、
  provenance確認、人間による明示的なreviewを要求する。
- local corpusの観察結果を、未審査のままcore ruleへ昇格しない。
- ルートカタログと `skills/` を同期する。
- commit前に `./scripts/validate-skills.sh` を実行する。
- commitを目的別に分け、force pushしない。
