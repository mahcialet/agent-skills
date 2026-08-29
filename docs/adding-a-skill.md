# Skillの追加

1. 一意なlowercase・hyphen区切りの名前を選ぶ。
2. `skills/<name>/SKILL.md` を作る。YAML `name` をディレクトリ名と一致させ、
   `description` に使用・非使用条件を書く。
3. portable frontmatterを最小限にし、provider tool名やmodel名を入れない。
4. 実行時references、scripts、examples、assetsをSkill配下に置く。
5. `README.md` と `NOTICE.md` を作り、参照元と変更内容を記録する。
6. positive、negative、安全性、portabilityのeval fixtureを追加する。
7. ルートREADMEの適切なcategoryへ一行だけ追加し、hosts、languages、stability、
   description、NOTICEリンクを載せる。
8. `./scripts/validate-skills.sh` と、利用可能なら
   `gh skill publish --dry-run` を実行する。
9. モノレポ外へコピーしたSkill単体で動くことを確認する。

最初のカタログSkillは `reader-first-editor` です。動作確認用placeholderや
hello-world Skillは追加せず、test fixtureを使ってください。
