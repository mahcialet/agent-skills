# Skillの追加

新しいSkillを追加するときは、複数の対応ホストで共有できるSkill本体、利用者向け文書、
第三者由来要素のattribution、eval、ルートカタログの内容を一致させる。

1. 一意なlowercase・hyphen区切りの名前を選ぶ。
2. `skills/<name>/SKILL.md` を作る。YAML `name` をディレクトリ名と一致させ、
   `description` に使う条件と使わない条件を書く。
3. 複数ホストで共有するfrontmatterは必要最小限にし、特定providerのtool名やmodel名を
   入れない。
4. Skillが実行時に読むreferences、scripts、examples、assetsをSkill配下に置く。
5. 利用者向けの `README.md` と `NOTICE.md` を作り、参照元、著作者表示、license、
   変更内容など、[Licensing](licensing.md)で定めた情報を記録する。
6. positive、negative、安全性、複数ホストでの利用（portability）を確認するeval fixtureを
   追加する。
7. `catalog.json` にcategory、hosts、languages、stability、短いdescriptionを追加し、
   `./scripts/generate-catalog.py` でルートREADMEを更新する。Skill名はfrontmatterに
   記載した値を正とし、補助metadataとの不一致はgeneratorが拒否する。
8. `./scripts/validate-skills.sh` と、利用可能なら
   `gh skill publish --dry-run` を実行する。
9. モノレポ外へコピーしたSkill単体で動くことを確認する。

最初にカタログへ掲載したSkillは `reader-first-editor` です。動作確認だけを目的とする
placeholderやhello-world Skillは追加せず、test fixtureを使ってください。
