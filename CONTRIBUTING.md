# Contributing

各Skillを、複数のホストで同じ内容から利用でき、単独でインストールでき、安全に起動できる
状態に保ってください。

## 変更の基本手順

1. [Skillの追加](docs/adding-a-skill.md)と `AGENTS.md` を読む。
2. Skillの正式なinstructionsを `skills/<name>/SKILL.md` に置き、ホスト別のコピーを
   手作業で作らない。
3. Skillが実行時に読むファイルを、Skillディレクトリ内に収める。
4. 第三者由来要素のattribution（出典・著作者表示など）とlicense noticeを、Skillの
   `NOTICE.md` とルートの `THIRD_PARTY_NOTICES.md` に記録する。
5. 挙動を変更するときは、examplesと評価用fixtureを追加する。
6. `./scripts/validate-skills.sh` と、利用可能なら
   `gh skill publish --dry-run` を実行する。

## 文書の言語

説明文書は日本語を基本とします。ホストがSkillを検出するためのfrontmatter、CLIの
command・option、ファイル名、schema key、識別子、license原文、保持が必要な引用は、
必要に応じて英語を維持してください。機能を説明するときは、planned、experimental、
implemented、verifiedのどの状態かを明記し、未実装の機能を利用可能と表現しないでください。

## corpusとruleの変更

`reader-first-editor` のcorpus候補を追加する場合は、出典、後から内容が変わらないsource
（immutableなsource）、取得日時、著者情報（authorship）、レビュー状況（review signal）、
権利状況（rights status）、raw textの有無、local-onlyかどうかを記録します。権利状況を
確認できない第三者の文章はpublicなfixtureへ追加せず、local-onlyまたはreference-onlyとして
扱ってください。候補を集めただけでは、Skillの挙動を変更してはいけません。

Skillの挙動を変えるルール（behavior-changing rule）を提案する場合は、次の要素を個別に
確認できるようにします。

- 複数の独立した支持例
- 修正すべきでない反例と境界例
- 適用する言語、genre（文書の種類）、読者、目的
- semantic preservation（意味保存）とunnecessary revision（不要な改稿）の回帰リスク
- 既存ruleとの重複と、頻度だけではなく、そのルールが成り立つ仕組み（成立機序）
- positive、negative、boundary fixtureと既存eval全件の結果

未説明の反例が残る提案は採用せず、`HOLD` または `NEEDS_MORE_EVIDENCE` とします。
corpus promotionとrule promotionの詳細は、
[corpus workflow](skills/reader-first-editor/docs/corpus-workflow.md)と
[rule promotion](skills/reader-first-editor/docs/rule-promotion.md)を参照してください。

commitは意味のある小さな単位に分けてください。カタログ変更、挙動変更、
無関係な整理は、互いに不可分な場合を除き、同じcommitに混ぜないでください。
