# アーキテクチャ

## Skillの配置

各Skillで最初に読むファイルは `skills/<skill-name>/SKILL.md` です。複数の対応ホストで
共有できるよう、実行に必要なinstructions、references、examples、scripts、noticesを
同じディレクトリ内に置きます。コピーしたSkillは、別のSkillや自身より上のパスに
依存せず、単独で動作します。

リポジトリのルートには、全Skillに共通する検証、インストール補助、カタログ、CI、
license索引、contribution方針を置きます。Skill固有の挙動を定めるinstructionsや処理は、
各Skill内に置きます。

## ホスト間のportable性

CodexとGitHub Copilotは同じ `SKILL.md` を使います。`agents/openai.yaml` のような
任意のホストmetadataだけに、挙動を定めるinstructionsを置いてはいけません。確認済みの
非互換を共通形式で扱えない場合に限り、provider adapterを検討します。

## 段階的な情報開示

`SKILL.md` には起動条件と処理手順を記載します。詳細な規則は、参照条件を明示した
小さなreferencesに分け、必要なものだけを読みます。examplesとeval fixtureには挙動を
記録しますが、起動のたびに必ず読み込む情報にはしません。

## Reader-First Editorの育成基盤（一部implemented）

現在の通常reviewが使うのは、Skillに同梱したreferencesとevalだけです。通常reviewから
local corpusを明示的に利用する機能は未実装です。

育成基盤では、schema v1、local data directoryの解決、state transition、audit log、
manual corpus CLI、public GitHub PRのreference-only収集、adversarial investigation bundle、
proposal draftを実装済みです。provider-neutralなregression plan・result取込み・report、
人間の承認artifact、限定したrule applyも実装済みです。

育成基盤では、配布される共通部分（Core）と利用者固有のデータ（Local）を分離します。

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

Local dataは、インストール済みSkillのsource directoryには保存できません。保存先はuser scopeを
既定とし、project scopeは明示された場合だけ使用します。候補収集やcorpus promotionを行っても、
Coreの `SKILL.md`、references、evalsは自動的には変更されません。通常reviewもLocalを暗黙に
読み込みません。

同じ入力から同じ結果を返す機械処理と、Agentが内容を判断する処理も分離します。

| 担当 | 責務 |
|---|---|
| Skill内のtool | 収集、正規化、provenance保存、state transition、schema validation、diff、audit、bundle・regression plan生成、result集約、apply gate |
| Agent | pattern仮説、反例探索、境界分析、semantic risk、保守的なrule proposal、provider上でのeval実行 |
| 人間 | rights判断、annotation、corpus promotion、regression結果の確認、behavior-changing ruleの最終承認 |

toolから特定providerのAPIやCLIを直接呼びません。Agent向けbundleとregression planは、Codexと
Copilotが共通利用できる形式にします。承認時にもproposalを直接変更せず、reportとexact diff hashを
固定した別artifactとして保存します。`rules apply` が変更するのは許可対象pathだけです。validatorが
失敗した場合はrollbackします。自動commit・pushは行いません。詳細は
[corpus workflow](../skills/reader-first-editor/docs/corpus-workflow.md)と
[Agent investigation](../skills/reader-first-editor/docs/agent-investigation.md)に記載します。

## Optional Japanese syntax sensor

GiNZA adapterはCoreの必須依存ではなく、明示的に起動したときだけ読み込むoptional componentです。
通常reviewの実行pathから、package install、model download、parse fixtureを切り離しています。
dependencyやmodelがない場合、またはloadやparseに失敗した場合は、処理を止めずに非致命の
availability resultとして記録し、LLM-onlyの処理を継続します。

sensorが返すのは、構造観測値、backend・model version、text hashです。可読性、RR label、曖昧性、
改稿の要否は決定しません。A/B集約でも特定providerを直接起動せず、CodexとGitHub Copilotで外部実行
したpaired observationを共通schemaから比較します。自動blockerがなく改善が観測された場合も人間の
確認を要求し、既定利用は有効化しません。
