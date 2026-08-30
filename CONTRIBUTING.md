# Contributing

各Skillをportable、単独インストール可能、安全に起動できる状態に保ってください。

## 変更の基本手順

1. [Skillの追加](docs/adding-a-skill.md)と `AGENTS.md` を読む。
2. `skills/<name>/SKILL.md` に置き、ホスト別に複製しない。
3. 実行時参照をSkillディレクトリ内に収める。
4. 第三者由来要素をSkillの `NOTICE.md` とルートの
   `THIRD_PARTY_NOTICES.md` に記録する。
5. 挙動変更にはexamplesと評価fixtureを追加する。
6. `./scripts/validate-skills.sh` と、利用可能なら
   `gh skill publish --dry-run` を実行する。

## 文書の言語

説明文書は日本語を基本とします。host discovery用のfrontmatter、CLI command・option、
file名、schema key、識別子、license原文、保持が必要な引用は、必要に応じて英語を
維持してください。未実装の機能は、planned、experimental、implemented、verifiedの
どの状態かを明記します。

## corpusとruleの変更

`reader-first-editor` のcorpus候補を追加する場合は、出典、immutableなsource、取得日時、
authorship、review signal、rights status、raw textの有無、local-onlyかどうかを記録します。
権利が不明なthird-party textはpublicなfixtureへ追加せず、local-onlyまたは
reference-onlyとして扱ってください。候補収集だけでSkillの挙動を変更してはいけません。

behavior-changing ruleを提案する場合は、次を分離してreviewできるようにします。

- 複数の独立した支持例
- 修正すべきでない反例と境界例
- 適用する言語、genre、読者、目的
- semantic preservationとunnecessary revisionの回帰リスク
- 既存ruleとの重複と、頻度以外の成立機序
- positive、negative、boundary fixtureと既存eval全件の結果

未説明の反例が残る提案は採用せず、`HOLD` または `NEEDS_MORE_EVIDENCE` とします。
corpus promotionとrule promotionの詳細は、
[corpus workflow](skills/reader-first-editor/docs/corpus-workflow.md)と
[rule promotion](skills/reader-first-editor/docs/rule-promotion.md)を参照してください。

commitは意味のある小さな単位に分けてください。カタログ変更、挙動変更、
無関係なcleanupは、互いに不可分な場合を除き、同じcommitに混ぜないでください。
