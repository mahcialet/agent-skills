# アーキテクチャ

## Source layout

各portable Skillの起点は `skills/<skill-name>/SKILL.md` です。実行に必要な
instructions、references、examples、scripts、noticesを同じディレクトリ内に置きます。
コピー後のSkillは、別Skillや自身より上のパスに依存しません。

ルートは共通検証、インストール補助、カタログ、CI、license索引、contribution方針を
持ちます。Skill固有の挙動を定めるinstructionsや処理は、各Skill内に置きます。

## Host portability

CodexとGitHub Copilotは同じ `SKILL.md` を使います。`agents/openai.yaml` のような
任意のホストmetadataに、唯一の挙動instructionsを置きません。確認済みの非互換を
共通形式で吸収できない場合に限りprovider adapterを検討します。

## Progressive disclosure

`SKILL.md` は起動契約とworkflowを持ちます。詳細規則は明示的に振り分けた小さな
referencesに分け、必要なものだけを読みます。examplesとeval fixtureは挙動を記録
しますが、毎回の起動で必ず読むcontextにはしません。
