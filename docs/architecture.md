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

## Reader-First Editorの育成基盤（planned）

この節は設計済み・未実装の構成を記録します。現在の通常reviewは、既存のbundled
referencesとevalだけを使用します。

育成基盤では、配布されるCoreと利用者固有のLocalを分離します。

```text
Core
├── 共通原則と言語別技法
├── bundled examples
└── bundled evals

Local
├── candidates
├── accepted / rejected records
├── promoted corpus
├── investigations
└── rule proposals
```

Local dataはインストール済みSkillのsource directoryへ保存しません。user scopeを既定とし、
project scopeは明示指定された場合だけ使用する計画です。候補収集やcorpus promotionにより、
Coreの `SKILL.md`、references、evalsが自動的に変更されることはありません。通常reviewも
Localを暗黙に読み込みません。

deterministicな処理とAgent reasoningの責務も分離します。

| 担当 | 責務 |
|---|---|
| Skill内のtool | 収集、正規化、provenance保存、state transition、schema validation、diff、audit、bundle生成 |
| Agent | pattern仮説、反例探索、境界分析、semantic risk、保守的なrule proposal |
| 人間 | rights判断、annotation、corpus promotion、behavior-changing ruleの最終承認 |

toolから特定providerのAPIやCLIを直接呼ばず、Agent向けbundleをCodexとCopilotで共通利用
できる形式にします。詳細は
[corpus workflow](../skills/reader-first-editor/docs/corpus-workflow.md)と
[Agent investigation](../skills/reader-first-editor/docs/agent-investigation.md)に記載します。
