# リポジトリ指示

## 適用範囲

この指示はリポジトリ全体に適用する。

## Skill設計

- `skills/<name>/SKILL.md` をportableなsource of truthにする。
- Codex版とCopilot版を手書きで複製しない。
- provider固有metadataを共通instructionsから分離する。
- 実行時参照を各Skillディレクトリ内に収める。
- ユーザーが明示的に編集を求めない限り、編集Skillを非破壊動作にする。

## 変更

- 第三者attributionとlicense noticeを保存する。
- 挙動変更時はexamplesとeval fixtureを更新する。
- ルートカタログと `skills/` を同期する。
- commit前に `./scripts/validate-skills.sh` を実行する。
- commitを目的別に分け、force pushしない。
