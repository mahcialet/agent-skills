# Contributing

各Skillをportable、単独インストール可能、安全に起動できる状態に保ってください。

1. [Skillの追加](docs/adding-a-skill.md)と `AGENTS.md` を読む。
2. `skills/<name>/SKILL.md` に置き、ホスト別に複製しない。
3. 実行時参照をSkillディレクトリ内に収める。
4. 第三者由来要素をSkillの `NOTICE.md` とルートの
   `THIRD_PARTY_NOTICES.md` に記録する。
5. 挙動変更にはexamplesと評価fixtureを追加する。
6. `./scripts/validate-skills.sh` と、利用可能なら
   `gh skill publish --dry-run` を実行する。

commitは意味のある小さな単位に分け、不可分でないカタログ変更・挙動変更・
無関係なcleanupを混ぜないでください。
