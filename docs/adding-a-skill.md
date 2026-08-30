# Skillの追加

新しいSkillを追加するときは、複数の対応ホストで共有できるSkill本体、利用者向け文書、
第三者由来要素のattribution、eval、ルートカタログの内容を一致させる。

1. 英小文字を使い、単語をハイフンで区切った一意な名前を選ぶ。
2. `skills/<name>/SKILL.md` を作る。YAML `name` をディレクトリ名と一致させ、
   `description` に使う条件と使わない条件を書く。
3. 複数ホストで共有するfrontmatterは必要最小限にし、特定のproviderだけが使うtool名やmodel名を
   入れない。
4. Skillが実行時に読むreferences、scripts、examples、assetsをSkill配下に置く。
5. 利用者向けの `README.md` と `NOTICE.md` を作り、参照元、著作者表示、license、
   変更内容など、[Licensing](licensing.md)で定めた情報を記録する。
6. positive、negative、安全性、複数ホストでの利用（portability）を確認するeval fixtureを
   追加する。
7. `catalog.json` にcategory、hosts、languages、stability、短いdescriptionを追加し、
   `./scripts/generate-catalog.py` でルートREADMEを更新する。Skill名にはfrontmatterに
   記載した値を使用する。補助metadataと値が異なる場合はgeneratorが拒否する。
8. `./scripts/validate-skills.sh` を実行する。利用環境で `gh skill` を使える場合は、
   `gh skill publish --dry-run` を実行する。
9. [インストール手順](installation.md)に従ってモノレポ外の一時ディレクトリへSkill全体を
   コピーする。対応ホストから明示起動し、追加ファイルを読み込めることと、READMEに記載した
   既定動作・変更範囲どおりに動くことを確認する。

最初にカタログへ掲載したSkillは `reader-first-editor` です。動作確認だけを目的とする
placeholderやhello-world Skillは追加せず、test fixtureを使ってください。
