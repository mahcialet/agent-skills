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

## Reader-First Editorの育成基盤（一部implemented）

schema v1、local data directoryの解決、state transition、audit log、manual corpus CLI、
public GitHub PRのreference-only収集、adversarial investigation bundle、proposal draftは
実装済みです。provider-neutralなregression plan・result取込み・report、人間の承認artifact、
限定したrule applyも実装済みです。通常reviewからの明示的なlocal corpus利用は未実装です。
現在の通常reviewは、既存のbundled referencesとevalだけを使用します。

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
├── rule proposals
├── regression plans / runs / reports
└── rule approvals
```

Local dataはインストール済みSkillのsource directoryへ保存できません。user scopeを既定とし、
project scopeは明示指定された場合だけ解決します。候補収集やcorpus promotionにより、
Coreの `SKILL.md`、references、evalsが自動的に変更されることはありません。通常reviewも
Localを暗黙に読み込みません。

deterministicな処理とAgent reasoningの責務も分離します。

| 担当 | 責務 |
|---|---|
| Skill内のtool | 収集、正規化、provenance保存、state transition、schema validation、diff、audit、bundle・regression plan生成、result集約、apply gate |
| Agent | pattern仮説、反例探索、境界分析、semantic risk、保守的なrule proposal、provider上でのeval実行 |
| 人間 | rights判断、annotation、corpus promotion、regression結果の確認、behavior-changing ruleの最終承認 |

toolから特定providerのAPIやCLIを直接呼ばず、Agent向けbundleとregression planをCodexと
Copilotで共通利用できる形式にします。承認はproposalを直接変更せず、reportとexact diff hashを
固定した別artifactとして保存します。`rules apply` は許可対象pathだけを変更し、validator失敗時は
rollbackします。自動commit・pushは行いません。詳細は
[corpus workflow](../skills/reader-first-editor/docs/corpus-workflow.md)と
[Agent investigation](../skills/reader-first-editor/docs/agent-investigation.md)に記載します。

## Optional Japanese syntax sensor

GiNZA adapterはCoreの必須依存ではなく、明示起動時だけ読み込むoptional componentです。通常reviewの
実行pathから、package install、model download、parse fixtureを分離します。dependency不在、model
不在、load失敗、parse失敗は非致命のavailability resultへ変換し、LLM-onlyの処理を継続します。

sensorは構造観測値とbackend・model version、text hashを返します。可読性、RR label、曖昧性、改稿
要否を決定しません。A/B集約も特定providerを直接起動せず、CodexとGitHub Copilotで外部実行した
paired observationを共通schemaから比較します。自動blockerがなく改善が観測されても人間の確認を
要求し、既定利用は有効化しません。
