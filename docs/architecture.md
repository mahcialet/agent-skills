# アーキテクチャ

## Skillの配置

各Skillで最初に読むファイルは `skills/<skill-name>/SKILL.md` です。複数の対応ホストで
共有できるよう、実行に必要な指示、`references`、`examples`、`scripts`、`NOTICE.md` などを
同じディレクトリ内に置きます。コピーしたSkillは、別のSkillや自身より上位のパスに
依存せず、単独で動作します。

リポジトリのルートには、全Skillに共通する検証、インストール補助、カタログ、CI、
ライセンス索引、コントリビューション方針を置きます。Skill固有の挙動を定める指示や処理は、
各Skill内に置きます。

リポジトリ内の `SKILL.md` が、各ホストで共有する編集元です。`install-local.sh` がコピーする場合は、
編集元を変えず、配置先の説明末尾だけにインストール元の短縮Git commit ID、commitのtreeとの違い、
またはcommit IDを取得できない理由を追加します。
CodexとGitHub Copilotで生成物を分けず、同じscopeでは同じ `.agents/skills/<name>` を共有します。
`--link` は編集元を直接参照するため、commit IDを説明へ追加しません。

現在使うSkillは `.agents/skills`、置換前のバックアップは探索範囲外の `.agents/backups` に置きます。
これにより、旧版のバックアップが別のSkill候補として表示される状態を避けます。コピーの
バックアップは置換前のファイルを保持しますが、リンクのバックアップはリンク自体だけを保持し、
リンク先の内容を固定しません。

<a id="ホスト間のportable性"></a>

## ホスト間で共通利用するための方針

CodexとGitHub Copilotは同じ `SKILL.md` を使います。`agents/openai.yaml` のような
任意のホスト固有のmetadataだけに、挙動を定める指示を置いてはいけません。確認済みの
非互換を共通形式で扱えない場合に限り、ホスト固有の調整層（provider adapter）を検討します。

## 段階的な情報開示

`SKILL.md` には起動条件と処理手順を記載します。詳細な規則は、参照条件を明示した
小さな参照ファイルに分け、必要なものだけを読みます。`examples` とeval fixtureには挙動を
記録しますが、起動のたびに必ず読み込む情報とは分けて扱います。

<a id="reader-first-editorの育成基盤一部implemented"></a>

## Reader-First Editorの育成基盤（一部実装済み）

現在の通常reviewが使うのは、Skillに同梱した参照ファイルとevalだけです。通常reviewから
local corpusを明示的に利用する機能は、まだ実装していません。

育成基盤では、次の機能を実装済みです。

- schema v1、local data directoryの解決、状態遷移（state transition）、監査ログ
- manual corpus CLI、public GitHub PRのreference-only収集
- adversarial investigation bundle、proposal draft
- provider-neutralなregression plan、resultの取込み、reportの作成
- 人間による承認artifact、対象を限定したrule apply

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

Local dataは、インストール済みSkillのsource directoryには保存できません。保存先にはuser scopeを
既定で使い、project scopeは明示された場合だけ使います。候補収集やcorpus promotionを行っても、
Coreの `SKILL.md`、`references`、`evals` は自動的には変更されません。通常reviewもLocalを暗黙に
読み込みません。

同じ入力から同じ結果を返す機械処理と、Agentが内容を判断する処理も分離します。

| 担当 | 責務 |
|---|---|
| Skill内のツール | 収集、正規化、来歴（provenance）の保存、状態遷移、schema検証、差分・監査記録、bundle・regression planの生成、resultの集約、適用前の検査（apply gate） |
| Agent | patternの仮説作成、反例探索、境界分析、意味を変えるリスク（semantic risk）の確認、保守的なrule proposal、provider上でのeval実行 |
| 人間 | 権利関係（rights）の判断、annotation、corpus promotion、regression結果の確認、behavior-changing ruleの最終承認 |

ツールから特定providerのAPIやCLIを直接呼びません。Agent向けbundleとregression planは、Codexと
Copilotが共通利用できる形式にします。承認時にもproposalを直接変更せず、reportとexact diff hashを
固定した別artifactとして保存します。`rules apply` が変更するのは許可されたpathだけです。validatorが
失敗した場合は変更を元に戻します（rollback）。自動commit・pushは行いません。詳細は
[corpus workflow](../skills/reader-first-editor/docs/corpus-workflow.md)と
[Agent investigation](../skills/reader-first-editor/docs/agent-investigation.md)に記載します。

<a id="optional-japanese-syntax-sensor"></a>

## 任意の日本語構文センサー

GiNZA adapterはCoreの必須依存ではなく、明示的に起動したときだけ読み込む任意の構成要素です。
通常reviewの実行pathから、packageのインストール、modelのダウンロード、fixtureの解析を切り離しています。
dependencyやmodelがない場合、またはloadやparseに失敗した場合も処理を止めません。利用できない
ことを非致命のavailability resultとして記録し、LLM-onlyの処理を継続します。

センサーが返すのは、構造観測値、backend・model version、text hashです。可読性、RR label、曖昧性、
改稿の要否は決定しません。A/B集約でも特定providerを直接起動せず、CodexとGitHub Copilotで外部実行
した対になる観測結果（paired observation）を、共通schemaで比較します。自動blockerがなく改善が観測された場合も人間の
確認を要求し、既定利用は有効化しません。
